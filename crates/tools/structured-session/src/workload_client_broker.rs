//! Mechanical bridge from short-lived workload-local client connections to
//! one daemon-owned protected target channel.
//!
//! This module has no grant logic. The daemon retains every bearer and the
//! admitted workload-client grant; this bridge only bounds, frames, and pairs
//! requests. The endpoint is not a daemon endpoint and never receives a
//! daemon pathname or credential.

use std::collections::{HashMap, hash_map::Entry};
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{SyncSender, sync_channel};
use std::sync::{Arc, Condvar, Mutex};
use std::thread;

use anyhow::{Context, Result, anyhow};
use ryeos_runtime::workload_client::{
    WORKLOAD_CLIENT_PROTOCOL, WorkloadClientBootFrame, WorkloadClientOutcome,
    WorkloadClientReadyFrame, WorkloadClientRequestFrame, WorkloadClientResponseFrame,
};

pub struct RunningWorkloadClientBroker {
    endpoint: String,
    stopping: Arc<AtomicBool>,
    slots: Arc<SlotPool>,
    accept_thread: Option<thread::JoinHandle<()>>,
}

impl RunningWorkloadClientBroker {
    pub fn endpoint(&self) -> &str {
        &self.endpoint
    }
}

impl Drop for RunningWorkloadClientBroker {
    fn drop(&mut self) {
        self.stopping.store(true, Ordering::Release);
        self.slots.ready.notify_all();
        // Wake a listener blocked in accept. The typed accept boundary rejects
        // namespace PID 1 as a client, but still returns from the syscall so
        // the loop can observe shutdown and release the exact socket inode.
        let _ = lillux::LocalDuplexStream::connect(Path::new(&self.endpoint));
        if let Some(thread) = self.accept_thread.take() {
            let _ = thread.join();
        }
    }
}

struct SlotPool {
    available: Mutex<usize>,
    ready: Condvar,
}

impl SlotPool {
    fn acquire(self: &Arc<Self>, stopping: &AtomicBool) -> Option<SlotGuard> {
        let mut available = self
            .available
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        while *available == 0 && !stopping.load(Ordering::Acquire) {
            available = self
                .ready
                .wait(available)
                .unwrap_or_else(|error| error.into_inner());
        }
        if stopping.load(Ordering::Acquire) {
            return None;
        }
        *available -= 1;
        Some(SlotGuard {
            pool: Arc::clone(self),
        })
    }
}

struct SlotGuard {
    pool: Arc<SlotPool>,
}

impl Drop for SlotGuard {
    fn drop(&mut self) {
        let mut available = self
            .pool
            .available
            .lock()
            .unwrap_or_else(|error| error.into_inner());
        *available += 1;
        self.pool.ready.notify_one();
    }
}

/// Start the broker after the daemon supplied its secret-free boot contract.
/// The returned endpoint is the only value forwarded to the workload.
pub fn start(
    mut daemon_channel: lillux::InheritedDuplexChannel,
) -> Result<RunningWorkloadClientBroker> {
    let boot: WorkloadClientBootFrame =
        ryeos_runtime::workload_client::read_frame(&mut daemon_channel)
            .context("read workload-client boot contract")?;
    boot.validate()?;

    // Lillux binds this below the native sandbox's private tmpfs and proves
    // that this bridge is namespace PID 1. Project/candidate content and a
    // host-visible same-UID directory never carry the endpoint.
    let listener = lillux::OwnerPrivateLocalDuplexListener::bind_isolated_runtime(
        ryeos_runtime::workload_client::WORKLOAD_CLIENT_BROKER_DIRECTORY_NAME,
        "w",
    )?;
    let endpoint = listener
        .endpoint()
        .to_str()
        .ok_or_else(|| anyhow!("workload-client endpoint path is not UTF-8"))?
        .to_owned();

    let ready = WorkloadClientReadyFrame {
        protocol: WORKLOAD_CLIENT_PROTOCOL.to_owned(),
        grant_digest: boot.grant_digest.clone(),
    };
    ready.validate()?;
    ryeos_runtime::workload_client::write_frame(&mut daemon_channel, &ready)
        .context("publish workload-client bridge readiness")?;

    let reader = daemon_channel
        .try_clone()
        .context("clone protected workload-client response channel")?;
    let writer = Arc::new(Mutex::new(daemon_channel));
    let pending: Arc<Mutex<HashMap<String, SyncSender<WorkloadClientResponseFrame>>>> =
        Arc::new(Mutex::new(HashMap::new()));
    let response_pending = Arc::clone(&pending);
    thread::Builder::new()
        .name("ryeos-workload-client-responses".to_owned())
        .spawn(move || read_daemon_responses(reader, response_pending))
        .context("start workload-client response reader")?;

    let slots = Arc::new(SlotPool {
        available: Mutex::new(usize::from(boot.max_in_flight)),
        ready: Condvar::new(),
    });
    let accept_writer = Arc::clone(&writer);
    let accept_pending = Arc::clone(&pending);
    let max_request_bytes = usize::try_from(boot.max_request_bytes)
        .context("workload-client request ceiling exceeds this platform")?;
    let stopping = Arc::new(AtomicBool::new(false));
    let accept_stopping = Arc::clone(&stopping);
    let accept_slots = Arc::clone(&slots);
    let accept_thread = thread::Builder::new()
        .name("ryeos-workload-client-accept".to_owned())
        .spawn(move || {
            loop {
                let Some(slot) = accept_slots.acquire(&accept_stopping) else {
                    return;
                };
                let stream = match listener.accept_isolated_descendant() {
                    Ok(stream) => stream,
                    Err(_) if accept_stopping.load(Ordering::Acquire) => return,
                    // Refuse an outside peer without retiring the endpoint for
                    // valid descendants. Lillux already consumed and closed the
                    // unauthorized connection before returning this error.
                    Err(_) => continue,
                };
                if accept_stopping.load(Ordering::Acquire) {
                    return;
                }
                let writer = Arc::clone(&accept_writer);
                let pending = Arc::clone(&accept_pending);
                if thread::Builder::new()
                    .name("ryeos-workload-client-invocation".to_owned())
                    .spawn(move || {
                        handle_local_invocation(stream, writer, pending, slot, max_request_bytes)
                    })
                    .is_err()
                {
                    // A failed spawn drops the closure and therefore its stream
                    // and slot guard without forwarding the request.
                    return;
                }
            }
        })
        .context("start workload-client accept loop")?;

    Ok(RunningWorkloadClientBroker {
        endpoint,
        stopping,
        slots,
        accept_thread: Some(accept_thread),
    })
}

fn handle_local_invocation(
    mut stream: lillux::LocalDuplexStream,
    writer: Arc<Mutex<lillux::InheritedDuplexChannel>>,
    pending: Arc<Mutex<HashMap<String, SyncSender<WorkloadClientResponseFrame>>>>,
    _slot: SlotGuard,
    max_request_bytes: usize,
) {
    let request: Result<WorkloadClientRequestFrame> =
        ryeos_runtime::workload_client::read_frame_bounded(&mut stream, max_request_bytes)
            .context("read workload-client invocation");
    let request = match request.and_then(|request| {
        request.validate()?;
        Ok(request)
    }) {
        Ok(request) => request,
        Err(error) => {
            let _ = write_local_failure(&mut stream, "invalid-request", error.to_string());
            return;
        }
    };
    let request_id = request.request_id.clone();
    let (response_sender, response_receiver) = sync_channel(1);
    {
        let mut pending = pending.lock().unwrap_or_else(|error| error.into_inner());
        match pending.entry(request_id.clone()) {
            Entry::Vacant(entry) => {
                entry.insert(response_sender);
            }
            Entry::Occupied(_) => {
                let _ = write_local_failure(
                    &mut stream,
                    &request_id,
                    "request id is already in flight".to_owned(),
                );
                return;
            }
        }
    }
    let sent = writer
        .lock()
        .map_err(|_| anyhow!("workload-client request writer is poisoned"))
        .and_then(|mut writer| ryeos_runtime::workload_client::write_frame(&mut *writer, &request));
    if let Err(error) = sent {
        pending
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .remove(&request_id);
        let _ = write_local_failure(&mut stream, &request_id, error.to_string());
        return;
    }
    let response = match response_receiver.recv() {
        Ok(response) => response,
        Err(_) => failure_response(
            &request_id,
            "broker-disconnected",
            "daemon workload-client channel closed".to_owned(),
        ),
    };
    let _ = ryeos_runtime::workload_client::write_frame(&mut stream, &response);
}

fn read_daemon_responses(
    mut reader: lillux::InheritedDuplexChannel,
    pending: Arc<Mutex<HashMap<String, SyncSender<WorkloadClientResponseFrame>>>>,
) {
    loop {
        let response: WorkloadClientResponseFrame =
            match ryeos_runtime::workload_client::read_frame(&mut reader) {
                Ok(response) => response,
                Err(_) => break,
            };
        if response.validate().is_err() {
            break;
        }
        let sender = pending
            .lock()
            .unwrap_or_else(|error| error.into_inner())
            .remove(&response.request_id);
        let Some(sender) = sender else {
            break;
        };
        if sender.send(response).is_err() {
            continue;
        }
    }
    let abandoned = {
        let mut pending = pending.lock().unwrap_or_else(|error| error.into_inner());
        std::mem::take(&mut *pending)
    };
    for (request_id, sender) in abandoned {
        let _ = sender.send(failure_response(
            &request_id,
            "broker-disconnected",
            "daemon workload-client channel closed".to_owned(),
        ));
    }
}

fn write_local_failure(
    stream: &mut lillux::LocalDuplexStream,
    request_id: &str,
    message: String,
) -> Result<()> {
    ryeos_runtime::workload_client::write_frame(
        stream,
        &failure_response(request_id, "broker-refused", message),
    )
}

fn failure_response(request_id: &str, code: &str, message: String) -> WorkloadClientResponseFrame {
    let request_id = if ryeos_runtime::workload_client::validate_request_id(request_id).is_ok() {
        request_id.to_owned()
    } else {
        "invalid-request".to_owned()
    };
    WorkloadClientResponseFrame {
        protocol: WORKLOAD_CLIENT_PROTOCOL.to_owned(),
        request_id,
        outcome: WorkloadClientOutcome::Failed {
            code: code.to_owned(),
            message: message
                .chars()
                .filter(|character| *character != '\0')
                .take(2_048)
                .collect(),
            retryable: false,
        },
    }
}
