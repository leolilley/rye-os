//! Operator-authorized promotion of an import stage to a consumer binding.

use std::sync::Arc;

use anyhow::Result;
use serde_json::Value;

use crate::handler_context::HandlerContext;
use crate::registry::ServiceDescriptor;
use ryeos_app::state::AppState;
use ryeos_executor::executor::ServiceAvailability;

pub type Request = ryeos_app::operator_external_content::BindRequest;

pub async fn handle(req: Request, ctx: HandlerContext, state: Arc<AppState>) -> Result<Value> {
    req.validate_consumer_request()?;
    let response = match req.consumer_kind {
        ryeos_app::operator_external_content::BindConsumerKind::InstalledBundle => {
            ryeos_app::operator_external_content::bind(state, ctx, req).await?
        }
        ryeos_app::operator_external_content::BindConsumerKind::PinnedProject => {
            ryeos_app::operator_authority::require_local_configured_operator(&state, &ctx)?;
            let project_snapshot_hash = req
                .project_snapshot_hash
                .as_deref()
                .expect("validated pinned-project request");
            let project_path = req
                .project_path
                .as_ref()
                .expect("validated pinned-project request");
            let preparation_state = Arc::clone(&state);
            let preparation_consumer_ref = req.consumer_ref.clone();
            let preparation_snapshot_hash = project_snapshot_hash.to_owned();
            let preparation_project_path = project_path.clone();
            let preparation_fingerprint = ctx.fingerprint.clone();
            let preparation_scopes = ctx.scopes.clone();
            let checkout_id = format!("external-content-bind-{}", uuid::Uuid::new_v4());
            let prepared = tokio::task::spawn_blocking(move || {
                ryeos_executor::execution::project_source::prepare_pinned_project_external_consumer(
                    &preparation_state,
                    &preparation_consumer_ref,
                    &preparation_snapshot_hash,
                    preparation_project_path,
                    preparation_fingerprint,
                    preparation_scopes,
                    &checkout_id,
                )
            })
            .await
            .map_err(|error| anyhow::anyhow!("project consumer preparation panicked: {error}"))??;
            ryeos_app::operator_external_content::bind_pinned_project(
                state,
                ctx,
                req,
                prepared.resolution(),
            )
            .await?
        }
    };
    Ok(serde_json::to_value(response)?)
}

pub const DESCRIPTOR: ServiceDescriptor = ServiceDescriptor {
    service_ref: "service:external-content/bind",
    endpoint: "external-content.bind",
    availability: ServiceAvailability::DaemonOnly,
    required_caps: &["ryeos.execute.service.external-content/bind"],
    handler: |params, ctx, state| {
        Box::pin(async move {
            let req = crate::handler_error::parse_request(params)?;
            handle(req, ctx, state).await
        })
    },
};
