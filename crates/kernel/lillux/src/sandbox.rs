//! Linux process confinement below product and protocol vocabulary.
//!
//! This module owns the raw namespace, mount, descriptor, `pivot_root`,
//! `no_new_privs`, seccomp, fork, exec, and wait mechanics used by higher
//! layers. Callers supply an already-authorized set of open descriptors and a
//! complete target view; Lillux does not discover tools, projects, bundles, or
//! policy from ambient paths.

use std::collections::{BTreeMap, BTreeSet};
use std::ffi::OsString;
use std::path::PathBuf;

/// Access granted to one exact descriptor-backed mount.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinuxSandboxMountAccess {
    ReadOnly,
    Writable,
}

/// One exact already-open source mounted into the private root.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinuxSandboxMount {
    pub source_fd: u32,
    pub destination: PathBuf,
    pub access: LinuxSandboxMountAccess,
    pub layer: u32,
}

/// A filtered view of one already-authorized directory mount. Parent entries
/// along `denied_paths` are fixed for this launch; permitted mounted children
/// retain the access of the original mount. No policy paths are chosen here.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinuxSandboxFixedParentView {
    pub destination: PathBuf,
    pub denied_paths: Vec<PathBuf>,
    pub max_entries: usize,
    pub max_depth: usize,
}

/// Descriptor-backed overlay workspace. The lower, upper, and work
/// descriptors are all retained by the caller through sandbox creation.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinuxSandboxOverlay {
    pub lower_fd: u32,
    /// Exact backend-private state directory containing `upper/` and `work/`.
    pub state_fd: u32,
    pub destination: PathBuf,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinuxSandboxNetwork {
    Host,
    Isolated,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinuxSandboxProcFilesystem {
    Empty,
    PidNamespace,
}

/// Final target-release boundary. EOF is refusal, never permission to run.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinuxSandboxLifecycle {
    Run,
    AwaitRelease {
        release_fd: u32,
        release_keepalive_fd: u32,
    },
}

/// Aggregate limits require a delegated cgroup-v2 authority. The first native
/// backend slice deliberately refuses this request until that exact authority
/// can be passed in; per-process rlimits are not represented as aggregate
/// containment.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LinuxSandboxAggregateLimits {
    pub max_processes: Option<u64>,
    pub max_memory_bytes: Option<u64>,
    pub max_cpu_micros_per_second: Option<u64>,
}

/// Complete low-level request for a private Linux execution view.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinuxSandboxRequest {
    pub executable: PathBuf,
    pub argv0: OsString,
    pub arguments: Vec<OsString>,
    pub cwd: PathBuf,
    pub environment: BTreeMap<OsString, OsString>,
    pub mounts: Vec<LinuxSandboxMount>,
    pub fixed_parent_views: Vec<LinuxSandboxFixedParentView>,
    pub overlay: Option<LinuxSandboxOverlay>,
    pub network: LinuxSandboxNetwork,
    pub private_tmp: bool,
    pub proc_filesystem: LinuxSandboxProcFilesystem,
    pub minimal_devices: bool,
    pub target_channels: Vec<(u32, u32)>,
    pub lifecycle: LinuxSandboxLifecycle,
    pub contain_process_group: bool,
    pub aggregate_limits: Option<LinuxSandboxAggregateLimits>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct LinuxSandboxInspection {
    pub descriptor_mounts: bool,
    pub fixed_parent_views: bool,
    pub overlay_workspace: bool,
    pub isolated_network: bool,
    pub private_root: bool,
    pub private_tmp: bool,
    pub minimal_devices: bool,
    pub exact_environment: bool,
    pub isolated_pid_namespace: bool,
    pub pid_namespace_proc: bool,
    pub process_group_containment: bool,
    pub aggregate_resource_isolation: bool,
}

impl LinuxSandboxInspection {
    /// Capabilities implemented by this Lillux backend when its runtime probe
    /// succeeds. This does not probe the current host; admission must use
    /// [`inspect_linux_sandbox`] before selecting the backend, and launch still
    /// fails closed if any kernel operation is unavailable.
    pub const fn declared_native_contract() -> Self {
        Self {
            descriptor_mounts: true,
            fixed_parent_views: true,
            overlay_workspace: true,
            isolated_network: true,
            private_root: true,
            private_tmp: true,
            minimal_devices: true,
            exact_environment: true,
            isolated_pid_namespace: true,
            pid_namespace_proc: true,
            process_group_containment: true,
            aggregate_resource_isolation: false,
        }
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinuxSandboxExit {
    Code(i32),
    Signal(i32),
}

/// Exact child process created at the final sandbox boundary.
#[derive(Debug)]
pub struct LinuxSandboxProcess {
    #[cfg(target_os = "linux")]
    pid: libc::pid_t,
}

impl LinuxSandboxProcess {
    pub fn child_pid(&self) -> u32 {
        #[cfg(target_os = "linux")]
        {
            self.pid as u32
        }
        #[cfg(not(target_os = "linux"))]
        {
            0
        }
    }

    pub fn wait(mut self) -> Result<LinuxSandboxExit, String> {
        #[cfg(target_os = "linux")]
        {
            let mut status = 0;
            loop {
                let waited = unsafe { libc::waitpid(self.pid, &mut status, 0) };
                if waited == self.pid {
                    self.pid = 0;
                    if libc::WIFEXITED(status) {
                        return Ok(LinuxSandboxExit::Code(libc::WEXITSTATUS(status)));
                    }
                    if libc::WIFSIGNALED(status) {
                        return Ok(LinuxSandboxExit::Signal(libc::WTERMSIG(status)));
                    }
                    return Err("sandbox target returned an unsupported wait status".to_string());
                }
                let error = std::io::Error::last_os_error();
                if error.raw_os_error() != Some(libc::EINTR) {
                    return Err(format!("wait for sandbox target: {error}"));
                }
            }
        }
        #[cfg(not(target_os = "linux"))]
        {
            let _ = &mut self;
            Err("Linux sandbox processes are unavailable on this platform".to_string())
        }
    }
}

#[cfg(target_os = "linux")]
impl Drop for LinuxSandboxProcess {
    fn drop(&mut self) {
        if self.pid > 0 {
            unsafe {
                libc::kill(self.pid, libc::SIGKILL);
                libc::waitpid(self.pid, std::ptr::null_mut(), 0);
            }
            self.pid = 0;
        }
    }
}

/// Generic overlay mutation observed below an exact upper directory.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum LinuxOverlayMutationKind {
    UpsertRegular {
        normalized_mode: u32,
        size: u64,
        sha256: String,
    },
    DeletePath,
    EnsureDirectory,
    OpaqueDirectory,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinuxOverlayMutation {
    pub path: String,
    pub kind: LinuxOverlayMutationKind,
}

/// Exact roots and optional upper-layer mutations for one overlay workspace.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinuxOverlayWorkspaceObservation {
    pub project_identity: String,
    pub state_identity: String,
    /// Exact child of the retained state authority containing every regular
    /// byte named by `mutations`. Present only for Observe.
    pub mutation_content_root: Option<String>,
    pub mutations: Vec<LinuxOverlayMutation>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum LinuxOverlayWorkspaceOperation {
    Create,
    Observe,
    Destroy,
}

/// Inspect whether the current Linux kernel permits the complete native
/// confinement floor. Inspection occurs in a throwaway child, never mutating
/// the caller's namespaces.
pub fn inspect_linux_sandbox() -> Result<LinuxSandboxInspection, String> {
    imp::inspect()
}

/// Enter a private execution view and create a held final target.
///
/// On success the calling process is itself inside the new user/mount/IPC/UTS
/// namespace and private root. This API is intended for a dedicated adapter
/// process, not an application daemon.
pub fn launch_linux_sandbox(request: LinuxSandboxRequest) -> Result<LinuxSandboxProcess, String> {
    imp::launch(request)
}

/// Operate on exact inherited overlay-workspace descriptors without reopening
/// an ambient path.
pub fn operate_linux_overlay_workspace(
    project_fd: u32,
    state_fd: u32,
    operation: LinuxOverlayWorkspaceOperation,
    max_mutations: usize,
) -> Result<LinuxOverlayWorkspaceObservation, String> {
    imp::workspace(project_fd, state_fd, operation, max_mutations)
}

/// Write a bounded protocol payload to an inherited descriptor without
/// transferring raw descriptor ownership to the caller.
pub fn write_inherited_descriptor(fd: u32, bytes: &[u8]) -> Result<(), String> {
    imp::write_descriptor(fd, bytes)
}

/// Read one exact sealed inherited memfd with an explicit byte ceiling.
pub fn read_sealed_inherited_descriptor(fd: u32, max_bytes: usize) -> Result<Vec<u8>, String> {
    imp::read_sealed_descriptor(fd, max_bytes)
}

/// Prove an inherited descriptor identifies the executable image currently
/// running this dedicated adapter process.
pub fn validate_current_executable_descriptor(fd: u32) -> Result<(), String> {
    imp::validate_current_executable(fd)
}

/// Prove an inherited descriptor is one connected Unix stream socket.
pub fn validate_connected_unix_stream_descriptor(fd: u32) -> Result<(), String> {
    imp::validate_connected_unix_stream(fd)
}

/// Exit using the exact child outcome without exposing platform process APIs
/// to protocol adapters.
pub fn exit_with_linux_sandbox_status(status: LinuxSandboxExit) -> ! {
    imp::exit_with_status(status)
}

#[cfg(not(target_os = "linux"))]
mod imp {
    use super::*;

    pub fn inspect() -> Result<LinuxSandboxInspection, String> {
        Err("native Linux sandboxing is unavailable on this platform".to_string())
    }

    pub fn launch(_request: LinuxSandboxRequest) -> Result<LinuxSandboxProcess, String> {
        Err("native Linux sandboxing is unavailable on this platform".to_string())
    }

    pub fn workspace(
        _project_fd: u32,
        _state_fd: u32,
        _operation: LinuxOverlayWorkspaceOperation,
        _max_mutations: usize,
    ) -> Result<LinuxOverlayWorkspaceObservation, String> {
        Err("native Linux overlay workspaces are unavailable on this platform".to_string())
    }

    pub fn write_descriptor(_fd: u32, _bytes: &[u8]) -> Result<(), String> {
        Err("inherited Unix descriptors are unavailable on this platform".to_string())
    }

    pub fn read_sealed_descriptor(_fd: u32, _max_bytes: usize) -> Result<Vec<u8>, String> {
        Err("sealed inherited descriptors are unavailable on this platform".to_string())
    }

    pub fn validate_current_executable(_fd: u32) -> Result<(), String> {
        Err("executable descriptors are unavailable on this platform".to_string())
    }

    pub fn validate_connected_unix_stream(_fd: u32) -> Result<(), String> {
        Err("Unix stream descriptors are unavailable on this platform".to_string())
    }

    pub fn exit_with_status(_status: LinuxSandboxExit) -> ! {
        std::process::exit(125)
    }
}

#[cfg(target_os = "linux")]
mod imp {
    use super::*;
    use sha2::{Digest as _, Sha256};
    use std::ffi::{CStr, CString, OsStr};
    use std::fs::File;
    use std::io::{Read as _, Write as _};
    use std::os::fd::{AsRawFd as _, FromRawFd as _, RawFd};
    use std::os::unix::ffi::OsStrExt as _;

    mod fixed_parents;

    const ROOT: &str = "/tmp";
    const OLD_ROOT: &str = "/tmp/.lillux-old-root";
    const SEALED_STAGING_NAME: &str = ".lillux-sealed-staging";
    const CHILD_READY: u8 = 0;
    const CHILD_ERROR: u8 = 1;
    const MAX_CHILD_ERROR_BYTES: usize = 64 * 1024;
    const MOUNT_ATTR_RDONLY: u64 = 0x0000_0001;
    const MOUNT_ATTR_NOSUID: u64 = 0x0000_0002;
    const MOUNT_ATTR_NODEV: u64 = 0x0000_0004;
    const AT_RECURSIVE: u32 = 0x8000;
    const OPEN_TREE_CLONE: libc::c_uint = 0x0000_0001;
    const OPEN_TREE_CLOEXEC: libc::c_uint = libc::O_CLOEXEC as libc::c_uint;
    const MOVE_MOUNT_F_EMPTY_PATH: libc::c_uint = 0x0000_0004;
    const MOVE_MOUNT_T_EMPTY_PATH: libc::c_uint = 0x0000_0040;

    #[repr(C)]
    struct MountAttr {
        attr_set: u64,
        attr_clr: u64,
        propagation: u64,
        userns_fd: u64,
    }

    #[repr(C)]
    struct OpenHow {
        flags: u64,
        mode: u64,
        resolve: u64,
    }

    const RESOLVE_NO_MAGICLINKS: u64 = 0x02;
    const RESOLVE_NO_SYMLINKS: u64 = 0x04;
    const RESOLVE_BENEATH: u64 = 0x08;

    pub fn inspect() -> Result<LinuxSandboxInspection, String> {
        // Real launches inherit authorities from before CLONE_NEWNS. A probe
        // that opens every source afterwards misses the kernel's rejection of
        // bind mounts belonging to the former mount namespace.
        let inherited_directory =
            crate::secure_fs::pin_canonical_mount_source(std::path::Path::new(ROOT))
                .map_err(|error| format!("pin inherited namespace probe: {error}"))?;
        let inherited_bytes = crate::sealed_memfd(c"lillux-mount-probe", b"exact sealed bytes")?;
        let mut report = [0; 2];
        syscall_zero(
            unsafe { libc::pipe2(report.as_mut_ptr(), libc::O_CLOEXEC) },
            "create sandbox probe report",
        )?;
        let pid = unsafe { libc::fork() };
        if pid < 0 {
            close_fd(report[0]);
            close_fd(report[1]);
            return Err(format!(
                "fork native sandbox inspection: {}",
                std::io::Error::last_os_error()
            ));
        }
        if pid == 0 {
            close_fd(report[0]);
            let result = (|| {
                enter_namespaces(LinuxSandboxNetwork::Isolated)?;
                let directory = reanchor_mount_source(inherited_directory.as_raw_fd())?;
                mount_private_root()?;
                create_minimal_devices()?;
                create_private_tmp()?;
                let staging = SealedSourceStaging::create()?;
                let bytes =
                    materialize_sealed_mount_source(inherited_bytes.as_raw_fd(), &staging.content)?;
                probe_inherited_descriptor_mounts(&directory, &bytes)?;
                staging.detach()?;
                probe_descriptor_mount()?;
                fixed_parents::probe()?;
                probe_overlay()?;
                probe_isolated_pid_child()?;
                Ok::<(), String>(())
            })();
            match &result {
                Ok(()) => {
                    let _ = write_all_fd(report[1], &[CHILD_READY]);
                }
                Err(error) => {
                    let _ = write_child_error(report[1], error);
                }
            }
            unsafe { libc::_exit(if result.is_ok() { 0 } else { 125 }) };
        }
        close_fd(report[1]);
        let outcome = read_child_ready(report[0]);
        close_fd(report[0]);
        let mut status = 0;
        if unsafe { libc::waitpid(pid, &mut status, 0) } != pid {
            return Err(format!(
                "wait for native sandbox inspection: {}",
                std::io::Error::last_os_error()
            ));
        }
        if !libc::WIFEXITED(status) || libc::WEXITSTATUS(status) != 0 {
            return Err(format!(
                "native sandbox kernel probe refused: {}",
                outcome.err().unwrap_or_else(
                    || "probe child terminated without a failure report".to_string()
                )
            ));
        }
        outcome?;
        Ok(LinuxSandboxInspection::declared_native_contract())
    }

    pub fn launch(mut request: LinuxSandboxRequest) -> Result<LinuxSandboxProcess, String> {
        validate_request(&request)?;
        if request.aggregate_limits.is_some() {
            return Err(
                "aggregate resource isolation requires a delegated cgroup-v2 authority".to_string(),
            );
        }
        enter_namespaces(request.network)?;
        // Re-prove the same inherited filesystem objects in the cloned
        // namespace before the private root hides /tmp. The retained original
        // descriptors remain the identity authority, never a caller pathname.
        let mut sources = reanchor_request_sources(&request)?;
        mount_private_root()?;
        let sealed_staging = request
            .mounts
            .iter()
            .any(|mount| !sources.contains_key(&mount.source_fd))
            .then(SealedSourceStaging::create)
            .transpose()?;
        for mount in &request.mounts {
            if let std::collections::btree_map::Entry::Vacant(entry) =
                sources.entry(mount.source_fd)
            {
                if mount.access != LinuxSandboxMountAccess::ReadOnly {
                    return Err("sealed mount source cannot grant writable access".to_string());
                }
                let staging = sealed_staging
                    .as_ref()
                    .ok_or_else(|| "sealed source lacks private staging authority".to_string())?;
                entry.insert(materialize_sealed_mount_source(
                    raw_fd(mount.source_fd)?,
                    &staging.content,
                )?);
            }
        }
        for mount in &mut request.mounts {
            mount.source_fd = sources[&mount.source_fd].as_raw_fd() as u32;
        }
        if let Some(overlay) = &mut request.overlay {
            overlay.lower_fd = sources[&overlay.lower_fd].as_raw_fd() as u32;
            overlay.state_fd = sources[&overlay.state_fd].as_raw_fd() as u32;
        }
        if request.minimal_devices {
            create_minimal_devices()?;
        }
        if request.private_tmp {
            create_private_tmp()?;
        }
        if let Some(overlay) = &request.overlay {
            create_directory_target(&rooted(&overlay.destination)?)?;
            mount_overlay(overlay)?;
        }
        let mut mounts = request.mounts.clone();
        mounts.sort_by(|left, right| {
            left.layer
                .cmp(&right.layer)
                .then_with(|| left.destination.cmp(&right.destination))
        });
        for (index, mount) in mounts.iter().enumerate() {
            // Source-backed ancestors must already contain their targets.
            // Creating a missing child after binding a live source would
            // mutate that source; precreating it before binding hides it.
            if !mounts[..index]
                .iter()
                .any(|parent| mount.destination.starts_with(&parent.destination))
            {
                create_target(
                    &rooted(&mount.destination)?,
                    descriptor_kind(mount.source_fd)?,
                )?;
            }
            bind_descriptor_mount(mount)
                .map_err(|error| format!("mount {}: {error}", mount.destination.display()))?;
            if let Some(view) = request
                .fixed_parent_views
                .iter()
                .find(|view| view.destination == mount.destination)
            {
                fixed_parents::install(mount, view, index)?;
            }
        }
        if let Some(staging) = sealed_staging {
            staging.detach()?;
        }
        let executable = rooted(&request.executable)?;
        ensure_regular_path(&executable, "sandbox executable")?;
        let cwd = rooted(&request.cwd)?;
        ensure_directory_path(&cwd, "sandbox cwd")?;
        spawn_target(request)
    }

    fn validate_request(request: &LinuxSandboxRequest) -> Result<(), String> {
        let staging_path = PathBuf::from(format!("/{SEALED_STAGING_NAME}"));
        if request
            .mounts
            .iter()
            .any(|mount| mount.destination.starts_with(&staging_path))
            || request.overlay.as_ref().is_some_and(|overlay| {
                overlay.destination.starts_with(&staging_path)
                    || staging_path.starts_with(&overlay.destination)
            })
        {
            return Err("mount conflicts with private sealed-source staging".to_string());
        }
        // Reserve the surface even for Empty; an admitted mount must not
        // silently replace that choice with a host procfs alias.
        {
            let proc_path = std::path::Path::new("/proc");
            if request
                .mounts
                .iter()
                .any(|mount| mount.destination.starts_with(proc_path))
                || request.overlay.as_ref().is_some_and(|overlay| {
                    overlay.destination.starts_with(proc_path)
                        || proc_path.starts_with(&overlay.destination)
                })
            {
                return Err("mount conflicts with reserved PID procfs".to_string());
            }
        }
        validate_absolute_path(&request.executable, "sandbox executable")?;
        validate_absolute_path(&request.cwd, "sandbox cwd")?;
        if request.argv0.as_bytes().is_empty() || request.argv0.as_bytes().contains(&0) {
            return Err("sandbox argv0 is empty or contains NUL".to_string());
        }
        for argument in &request.arguments {
            if argument.as_bytes().contains(&0) {
                return Err("sandbox argument contains NUL".to_string());
            }
        }
        for (name, value) in &request.environment {
            if name.as_bytes().is_empty()
                || name.as_bytes().contains(&0)
                || name.as_bytes().contains(&b'=')
                || value.as_bytes().contains(&0)
            {
                return Err("sandbox environment contains an invalid entry".to_string());
            }
        }
        let mut destinations = BTreeSet::new();
        let mut descriptor_roles = BTreeSet::new();
        for mount in &request.mounts {
            validate_inherited_fd(mount.source_fd, "sandbox mount")?;
            descriptor_roles.insert(mount.source_fd);
            validate_absolute_path(&mount.destination, "sandbox mount destination")?;
            if mount.destination == PathBuf::from("/") {
                return Err("a descriptor mount cannot replace the private root".to_string());
            }
            if !destinations.insert(mount.destination.clone()) {
                return Err("sandbox mount destinations must be unique".to_string());
            }
        }
        fixed_parents::validate(request)?;
        if let Some(overlay) = &request.overlay {
            for fd in [overlay.lower_fd, overlay.state_fd] {
                validate_inherited_directory(fd, "sandbox overlay")?;
                if !descriptor_roles.insert(fd) {
                    return Err(
                        "descriptor is aliased across mount and overlay authority roles"
                            .to_string(),
                    );
                }
            }
            validate_absolute_path(&overlay.destination, "sandbox overlay destination")?;
            if overlay.destination == PathBuf::from("/")
                || !destinations.insert(overlay.destination.clone())
            {
                return Err("sandbox overlay destination is invalid or duplicated".to_string());
            }
        }
        let mut previous_target = None;
        for (source, target) in &request.target_channels {
            let (source, target) = (*source, *target);
            validate_inherited_fd(source, "sandbox target channel")?;
            let _ = raw_fd(target)?;
            if !descriptor_roles.insert(source) {
                return Err("target-channel descriptor aliases filesystem authority".to_string());
            }
            if matches!(target, 1 | 2) || previous_target.is_some_and(|previous| previous >= target)
            {
                return Err(
                    "sandbox target channels must be uniquely target-fd sorted and cannot replace stdout/stderr"
                        .to_string(),
                );
            }
            previous_target = Some(target);
        }
        match request.lifecycle {
            LinuxSandboxLifecycle::Run => {}
            LinuxSandboxLifecycle::AwaitRelease {
                release_fd,
                release_keepalive_fd,
            } => {
                validate_inherited_fd(release_fd, "sandbox release reader")?;
                validate_inherited_fd(release_keepalive_fd, "sandbox release keepalive")?;
                if !descriptor_roles.insert(release_fd)
                    || !descriptor_roles.insert(release_keepalive_fd)
                {
                    return Err(
                        "sandbox release descriptors alias another authority role".to_string()
                    );
                }
            }
        }
        for (source, target) in &request.target_channels {
            if *target > 2 && target != source && descriptor_roles.contains(target) {
                return Err(
                    "sandbox target channel destination aliases an inherited authority descriptor"
                        .to_string(),
                );
            }
        }
        Ok(())
    }

    fn enter_namespaces(network: LinuxSandboxNetwork) -> Result<(), String> {
        let uid = unsafe { libc::getuid() };
        let gid = unsafe { libc::getgid() };
        syscall_zero(
            unsafe { libc::unshare(libc::CLONE_NEWUSER) },
            "create user namespace",
        )?;
        write_proc_mapping("/proc/self/setgroups", "deny\n", true)?;
        write_proc_mapping("/proc/self/uid_map", &format!("0 {uid} 1\n"), false)?;
        write_proc_mapping("/proc/self/gid_map", &format!("0 {gid} 1\n"), false)?;
        syscall_zero(
            unsafe { libc::setresgid(0, 0, 0) },
            "enter mapped sandbox gid",
        )?;
        syscall_zero(
            unsafe { libc::setresuid(0, 0, 0) },
            "enter mapped sandbox uid",
        )?;
        let mut flags =
            libc::CLONE_NEWNS | libc::CLONE_NEWIPC | libc::CLONE_NEWUTS | libc::CLONE_NEWPID;
        if network == LinuxSandboxNetwork::Isolated {
            flags |= libc::CLONE_NEWNET;
        }
        syscall_zero(unsafe { libc::unshare(flags) }, "create sandbox namespaces")?;
        mount_raw(None, "/", None, libc::MS_REC | libc::MS_PRIVATE, None)
            .map_err(|error| format!("make sandbox mount propagation private: {error}"))
    }

    fn write_proc_mapping(path: &str, value: &str, missing_is_ok: bool) -> Result<(), String> {
        match std::fs::write(path, value.as_bytes()) {
            Ok(()) => Ok(()),
            Err(error) if missing_is_ok && error.raw_os_error() == Some(libc::ENOENT) => Ok(()),
            Err(error) => Err(format!("write sandbox identity mapping {path}: {error}")),
        }
    }

    fn mount_private_root() -> Result<(), String> {
        mount_raw(
            Some("tmpfs"),
            ROOT,
            Some("tmpfs"),
            libc::MS_NOSUID | libc::MS_NODEV,
            Some("mode=0755"),
        )
        .map_err(|error| format!("mount private sandbox root: {error}"))?;
        mkdir_one(&format!("{ROOT}/proc"), 0o555)
            .map_err(|error| format!("create private proc mountpoint: {error}"))?;
        mkdir_path(OLD_ROOT, 0o700)
    }

    // Keep the native backend aligned with the already-admitted mount-source
    // classes. Callback protocols may carry an exact filesystem Unix socket;
    // this does not grant a socket to callback-free or captured-only tools.
    use crate::secure_fs::OpenMountEntryKind as DescriptorKind;

    fn mount_source_stat(fd: RawFd) -> Result<libc::stat, String> {
        let mut stat = std::mem::MaybeUninit::<libc::stat>::uninit();
        syscall_zero(
            unsafe { libc::fstat(fd, stat.as_mut_ptr()) },
            "inspect mount source",
        )?;
        Ok(unsafe { stat.assume_init() })
    }

    fn reanchor_mount_source(fd: RawFd) -> Result<File, String> {
        let path = std::fs::read_link(format!("/proc/self/fd/{fd}"))
            .map_err(|error| format!("locate inherited mount descriptor: {error}"))?;
        reanchor_mount_source_at(fd, &path)
    }

    fn reanchor_mount_source_at(fd: RawFd, path: &std::path::Path) -> Result<File, String> {
        let expected = mount_source_stat(fd)?;
        let source = crate::secure_fs::pin_canonical_mount_source(path)
            .map_err(|error| format!("pin mount source in cloned namespace: {error}"))?;
        let observed = mount_source_stat(source.as_raw_fd())?;
        // open_tree cannot clone a vfsmount owned by the former namespace.
        // A kernel-reported path is only a locator: a replacement, symlink,
        // deleted object, or inaccessible source must fail, not authorize new
        // bytes. The original fd pins the inode against reuse throughout this
        // comparison; only this newly proven fd is subsequently mounted.
        if expected.st_dev != observed.st_dev
            || expected.st_ino != observed.st_ino
            || expected.st_mode & libc::S_IFMT != observed.st_mode & libc::S_IFMT
        {
            return Err("mount source changed across namespace transition".to_string());
        }
        Ok(source)
    }

    fn mount_source_is_sealed(fd: RawFd) -> Result<bool, String> {
        let flags = unsafe { libc::fcntl(fd, libc::F_GETFL) };
        if flags < 0 {
            return Err(format!(
                "inspect mount source flags: {}",
                std::io::Error::last_os_error()
            ));
        }
        if flags & libc::O_PATH != 0 {
            return Ok(false);
        }
        let seals = unsafe { libc::fcntl(fd, libc::F_GET_SEALS) };
        if seals < 0 {
            let error = std::io::Error::last_os_error();
            if error.raw_os_error() == Some(libc::EINVAL) {
                return Ok(false);
            }
            return Err(format!("inspect mount source seals: {error}"));
        }
        let required =
            libc::F_SEAL_SEAL | libc::F_SEAL_SHRINK | libc::F_SEAL_GROW | libc::F_SEAL_WRITE;
        Ok(seals & required == required)
    }

    fn reanchor_request_sources(
        request: &LinuxSandboxRequest,
    ) -> Result<BTreeMap<u32, File>, String> {
        let mut descriptors = request
            .mounts
            .iter()
            .map(|mount| mount.source_fd)
            .collect::<BTreeSet<_>>();
        if let Some(overlay) = &request.overlay {
            descriptors.extend([overlay.lower_fd, overlay.state_fd]);
        }
        let mut sources = BTreeMap::new();
        for descriptor in descriptors {
            let fd = raw_fd(descriptor)?;
            if descriptor_kind(descriptor)? == DescriptorKind::Regular
                && mount_source_is_sealed(fd)?
            {
                // One source may have several destinations. Check every use
                // before deduplication: a preceding read-only alias must not
                // let a later writable alias reuse the private byte copy.
                if request.mounts.iter().any(|mount| {
                    mount.source_fd == descriptor
                        && mount.access != LinuxSandboxMountAccess::ReadOnly
                }) {
                    return Err("sealed mount source cannot grant writable access".to_string());
                }
                continue;
            }
            sources.insert(descriptor, reanchor_mount_source(fd)?);
        }
        Ok(sources)
    }

    struct SealedSourceStaging {
        root: crate::PinnedDirectory,
        mountpoint: crate::PinnedDirectory,
        content: crate::PinnedDirectory,
    }

    impl SealedSourceStaging {
        fn create() -> Result<Self, String> {
            let root = crate::PinnedDirectory::open(std::path::Path::new(ROOT))
                .map_err(|error| error.to_string())?
                .ok_or_else(|| "private materialization root is missing".to_string())?;
            let mountpoint = root
                .create_child(OsStr::new(SEALED_STAGING_NAME), 0o700)
                .map_err(|error| format!("create private sealed staging: {error}"))?;
            let path = root.path().join(SEALED_STAGING_NAME);
            mount_raw(
                Some("tmpfs"),
                path_string(&path)?,
                Some("tmpfs"),
                libc::MS_NOSUID | libc::MS_NODEV,
                Some("mode=0700"),
            )
            .map_err(|error| format!("mount private sealed staging: {error}"))?;
            let content = root
                .open_child_directory(OsStr::new(SEALED_STAGING_NAME))
                .map_err(|error| error.to_string())?
                .ok_or_else(|| "private sealed staging mount disappeared".to_string())?;
            Ok(Self {
                root,
                mountpoint,
                content,
            })
        }

        fn detach(self) -> Result<(), String> {
            let name = OsStr::new(SEALED_STAGING_NAME);
            let current = self
                .root
                .open_child_directory(name)
                .map_err(|error| error.to_string())?
                .ok_or_else(|| "sealed staging disappeared before detach".to_string())?;
            if !self
                .content
                .is_same_directory(&current)
                .map_err(|error| error.to_string())?
            {
                return Err("sealed staging mount identity changed".to_string());
            }
            // Do not unlink source files: that marks the executable dentry
            // deleted even through its admitted bind mount, breaking self
            // lookup. Detach the private filesystem instead. Only the exact
            // read-only target mounts keep these linked inodes alive.
            unmount_path(&self.root.path().join(name))?;
            if !self
                .root
                .remove_empty_child_if_same(name, &self.mountpoint)
                .map_err(|error| format!("remove detached sealed mountpoint: {error:#}"))?
            {
                return Err("detached sealed mountpoint is not empty".to_string());
            }
            Ok(())
        }
    }

    fn materialize_sealed_mount_source(
        fd: RawFd,
        root: &crate::PinnedDirectory,
    ) -> Result<File, String> {
        use std::os::unix::fs::FileExt as _;

        if !mount_source_is_sealed(fd)? {
            return Err("private byte materialization requires a sealed source".to_string());
        }
        let source = unsafe { File::from_raw_fd(duplicate_fd(fd)?) };
        let metadata = source
            .metadata()
            .map_err(|error| format!("inspect sealed mount: {error}"))?;
        if !metadata.is_file() {
            return Err("sealed mount source is not a regular file".to_string());
        }
        let name = OsString::from(format!(".lillux-sealed-source-{fd}"));
        let root_fd = root
            .try_clone_descriptor()
            .map_err(|error| format!("retain private materialization root: {error}"))?;
        let encoded = c_string(&name, "private sealed source")?;
        let output_fd = unsafe {
            libc::openat(
                root_fd.as_raw_fd(),
                encoded.as_ptr(),
                libc::O_RDWR | libc::O_CREAT | libc::O_EXCL | libc::O_NOFOLLOW | libc::O_CLOEXEC,
                0o600,
            )
        };
        if output_fd < 0 {
            return Err(format!(
                "create private sealed source: {}",
                std::io::Error::last_os_error()
            ));
        }
        let mut output = unsafe { File::from_raw_fd(output_fd) };
        // Copy only the immutable, already-admitted length with bounded memory.
        // Positional reads do not consume the sender's shared file offset.
        let mut offset = 0;
        let mut buffer = [0_u8; 64 * 1024];
        while offset < metadata.len() {
            let limit = (metadata.len() - offset).min(buffer.len() as u64) as usize;
            let count = source
                .read_at(&mut buffer[..limit], offset)
                .map_err(|error| format!("read sealed mount bytes: {error}"))?;
            if count == 0 {
                return Err("sealed mount source ended before its exact length".to_string());
            }
            output
                .write_all(&buffer[..count])
                .map_err(|error| format!("write private sealed mount: {error}"))?;
            offset += count as u64;
        }
        let mode = mount_source_stat(fd)?.st_mode & 0o555;
        syscall_zero(
            unsafe { libc::fchmod(output.as_raw_fd(), mode) },
            "restrict private sealed mount",
        )?;
        let pinned_fd = unsafe {
            libc::openat(
                root_fd.as_raw_fd(),
                encoded.as_ptr(),
                libc::O_PATH | libc::O_NOFOLLOW | libc::O_CLOEXEC,
            )
        };
        if pinned_fd < 0 {
            return Err(format!(
                "retain private sealed source: {}",
                std::io::Error::last_os_error()
            ));
        }
        let pinned = unsafe { File::from_raw_fd(pinned_fd) };
        // No write-open handle may survive into exec, including in the adapter
        // parent: Linux correctly refuses ETXTBSY while such a handle exists.
        drop(output);
        // Keep the source name until move_mount: the kernel refuses attaching
        // an unlinked source. The caller detaches the whole private staging
        // filesystem after mounting, preserving linked executable identity
        // without exposing this setup alias to the workload.
        Ok(pinned)
    }

    fn descriptor_kind(fd: u32) -> Result<DescriptorKind, String> {
        let file = unsafe { File::from_raw_fd(duplicate_fd(raw_fd(fd)?)?) };
        crate::secure_fs::open_mount_entry_kind(&file)
            .map_err(|error| format!("inspect admitted mount descriptor: {error}"))
    }

    fn create_target(path: &PathBuf, kind: DescriptorKind) -> Result<(), String> {
        match kind {
            DescriptorKind::Directory => create_directory_target(path),
            DescriptorKind::Regular | DescriptorKind::UnixSocket => create_regular_target(path),
        }
    }

    fn create_directory_target(path: &PathBuf) -> Result<(), String> {
        let parent = path
            .parent()
            .ok_or_else(|| "sandbox directory target has no parent".to_string())?;
        mkdir_path(path_string(parent)?, 0o755)?;
        match mkdir_one(path_string(path)?, 0o755) {
            Ok(()) => Ok(()),
            Err(error) if error.raw_os_error() == Some(libc::EEXIST) => {
                ensure_directory_path(path, "sandbox mount target")
            }
            Err(error) => Err(format!(
                "create sandbox mount target {}: {error}",
                path.display()
            )),
        }
    }

    fn create_regular_target(path: &PathBuf) -> Result<(), String> {
        let parent = path
            .parent()
            .ok_or_else(|| "sandbox file target has no parent".to_string())?;
        mkdir_path(path_string(parent)?, 0o755)?;
        let c_path = c_string(path.as_os_str(), "sandbox file target")?;
        let fd = unsafe {
            libc::open(
                c_path.as_ptr(),
                libc::O_CREAT | libc::O_EXCL | libc::O_WRONLY | libc::O_CLOEXEC | libc::O_NOFOLLOW,
                0o600,
            )
        };
        if fd >= 0 {
            unsafe { libc::close(fd) };
            return Ok(());
        }
        let error = std::io::Error::last_os_error();
        if error.raw_os_error() == Some(libc::EEXIST) {
            ensure_regular_path(path, "sandbox mount target")
        } else {
            Err(format!(
                "create sandbox mount target {}: {error}",
                path.display()
            ))
        }
    }

    fn mkdir_path(path: &str, mode: libc::mode_t) -> Result<(), String> {
        let path = PathBuf::from(path);
        let mut current = PathBuf::from("/");
        for component in path.components().skip(1) {
            let std::path::Component::Normal(component) = component else {
                return Err("sandbox directory path is not normalized".to_string());
            };
            current.push(component);
            match mkdir_one(path_string(&current)?, mode) {
                Ok(()) => {}
                Err(error) if error.raw_os_error() == Some(libc::EEXIST) => {
                    ensure_directory_path(&current, "sandbox directory")?;
                }
                Err(error) => {
                    return Err(format!(
                        "create sandbox directory {}: {error}",
                        current.display()
                    ));
                }
            }
        }
        Ok(())
    }

    fn mkdir_one(path: &str, mode: libc::mode_t) -> std::io::Result<()> {
        let path =
            CString::new(path).map_err(|_| std::io::Error::from_raw_os_error(libc::EINVAL))?;
        if unsafe { libc::mkdir(path.as_ptr(), mode) } == 0 {
            Ok(())
        } else {
            Err(std::io::Error::last_os_error())
        }
    }

    fn create_private_tmp() -> Result<(), String> {
        let target = format!("{ROOT}/tmp");
        mkdir_path(&target, 0o1777)?;
        mount_raw(
            Some("tmpfs"),
            &target,
            Some("tmpfs"),
            libc::MS_NOSUID | libc::MS_NODEV,
            Some("mode=1777"),
        )
        .map_err(|error| format!("mount private sandbox tmp: {error}"))
    }

    fn create_minimal_devices() -> Result<(), String> {
        let dev = format!("{ROOT}/dev");
        mkdir_path(&dev, 0o755)?;
        mount_raw(
            Some("tmpfs"),
            &dev,
            Some("tmpfs"),
            libc::MS_NOSUID,
            Some("mode=0755"),
        )
        .map_err(|error| format!("mount minimal device filesystem: {error}"))?;
        for name in ["null", "zero", "random", "urandom"] {
            let source = format!("/dev/{name}");
            let source_c = CString::new(source.as_str()).expect("static device path");
            let fd = unsafe {
                libc::open(
                    source_c.as_ptr(),
                    libc::O_PATH | libc::O_NOFOLLOW | libc::O_CLOEXEC,
                )
            };
            if fd < 0 {
                return Err(format!(
                    "open minimal device {source}: {}",
                    std::io::Error::last_os_error()
                ));
            }
            let file = unsafe { File::from_raw_fd(fd) };
            let target = PathBuf::from(format!("{dev}/{name}"));
            create_regular_target(&target)?;
            bind_fd_to_path(file.as_raw_fd(), &target, false)?;
            // Device nodes remain read-only and non-setuid, but setting NODEV
            // on their bind mounts would make the deliberately admitted
            // `/dev/null`, `/dev/zero`, and random devices unusable.
            set_mount_attributes(&target, true, false, false)?;
            prove_minimal_device_usable(&target)?;
        }
        Ok(())
    }

    fn prove_minimal_device_usable(target: &PathBuf) -> Result<(), String> {
        let target = c_string(target.as_os_str(), "minimal device")?;
        let fd = unsafe {
            libc::open(
                target.as_ptr(),
                libc::O_RDONLY | libc::O_NONBLOCK | libc::O_CLOEXEC | libc::O_NOFOLLOW,
            )
        };
        if fd < 0 {
            return Err(format!(
                "open admitted minimal device after mount hardening: {}",
                std::io::Error::last_os_error()
            ));
        }
        close_fd(fd);
        Ok(())
    }

    fn probe_overlay() -> Result<(), String> {
        let probe = format!("{ROOT}/.overlay-probe");
        for name in ["lower", "state/upper", "state/work", "final"] {
            mkdir_path(&format!("{probe}/{name}"), 0o700)?;
        }
        let lower = crate::PinnedDirectory::open(std::path::Path::new(&format!("{probe}/lower")))
            .map_err(|error| error.to_string())?
            .ok_or_else(|| "overlay probe lower is missing".to_string())?;
        let state = crate::PinnedDirectory::open(std::path::Path::new(&format!("{probe}/state")))
            .map_err(|error| error.to_string())?
            .ok_or_else(|| "overlay probe state is missing".to_string())?;
        lower
            .atomic_write_if_same(OsStr::new("copy-up"), None, b"lower", 0o600)
            .map_err(|error| error.to_string())?;
        let lower_fd = lower
            .try_clone_descriptor()
            .map_err(|error| error.to_string())?;
        let state_fd = state
            .try_clone_descriptor()
            .map_err(|error| error.to_string())?;
        // Probe the production construction, including its private staging
        // point and descriptor move. A parallel hand-written overlay mount
        // misses setup regressions in the path actual workspaces use.
        mount_overlay(&LinuxSandboxOverlay {
            lower_fd: lower_fd.as_raw_fd() as u32,
            state_fd: state_fd.as_raw_fd() as u32,
            destination: PathBuf::from("/.overlay-probe/final"),
        })?;
        let visible = format!("{probe}/final/copy-up");
        if std::fs::read(&visible).map_err(|error| error.to_string())? != b"lower" {
            return Err("overlay probe changed lower content".into());
        }
        std::fs::write(&visible, b"upper").map_err(|error| error.to_string())?;
        if std::fs::read(format!("{probe}/lower/copy-up")).map_err(|error| error.to_string())?
            != b"lower"
            || std::fs::read(format!("{probe}/state/upper/copy-up"))
                .map_err(|error| error.to_string())?
                != b"upper"
        {
            return Err("overlay probe did not preserve private copy-up".into());
        }
        unmount_path(&PathBuf::from(format!("{probe}/final")))
    }

    fn probe_inherited_descriptor_mounts(directory: &File, bytes: &File) -> Result<(), String> {
        for (source, destination) in [
            (directory, "/.inherited-directory-probe"),
            (bytes, "/tmp/.sealed-bytes-probe"),
        ] {
            create_target(
                &rooted(&PathBuf::from(destination))?,
                descriptor_kind(source.as_raw_fd() as u32)?,
            )?;
            bind_descriptor_mount(&LinuxSandboxMount {
                source_fd: source.as_raw_fd() as u32,
                destination: PathBuf::from(destination),
                access: LinuxSandboxMountAccess::ReadOnly,
                layer: 0,
            })
            .map_err(|error| format!("probe mount {destination}: {error}"))?;
        }
        let path = format!("{ROOT}/tmp/.sealed-bytes-probe");
        if std::fs::read(&path).map_err(|error| format!("read sealed mount probe: {error}"))?
            != b"exact sealed bytes"
        {
            return Err("sealed mount probe changed bytes".to_string());
        }
        let encoded = CString::new(path).expect("static probe path");
        let writable = unsafe { libc::open(encoded.as_ptr(), libc::O_WRONLY | libc::O_CLOEXEC) };
        if writable >= 0 {
            close_fd(writable);
            return Err("sealed mount probe admitted a writable handle".to_string());
        }
        if std::io::Error::last_os_error().raw_os_error() != Some(libc::EROFS) {
            return Err("sealed mount probe did not prove read-only mount enforcement".to_string());
        }
        // The inherited probe source is /tmp, the ancestor of this fresh
        // sandbox root. Its recursive clone also retains the setup subtree's
        // mounts. Drop that probe-only alias after proving attachment, before
        // removing the sealed staging mountpoint; otherwise the cloned mount
        // keeps its underlying dentry busy. The sealed-byte target remains
        // attached, exactly as it does in a real launch.
        unmount_path(&rooted(&PathBuf::from("/.inherited-directory-probe"))?)?;
        Ok(())
    }

    fn probe_descriptor_mount() -> Result<(), String> {
        let source = PathBuf::from(format!("{ROOT}/.descriptor-probe-source"));
        let target = PathBuf::from(format!("{ROOT}/.descriptor-probe-target"));
        create_regular_target(&source)?;
        create_regular_target(&target)?;
        let source_path = c_string(source.as_os_str(), "descriptor probe source")?;
        let source_fd = unsafe {
            libc::open(
                source_path.as_ptr(),
                libc::O_PATH | libc::O_NOFOLLOW | libc::O_CLOEXEC,
            )
        };
        if source_fd < 0 {
            return Err(format!(
                "open descriptor-mount probe source: {}",
                std::io::Error::last_os_error()
            ));
        }
        let source = unsafe { File::from_raw_fd(source_fd) };
        bind_descriptor_mount(&LinuxSandboxMount {
            source_fd: u32::try_from(source.as_raw_fd())
                .map_err(|_| "descriptor probe source exceeds u32".to_string())?,
            destination: PathBuf::from("/.descriptor-probe-target"),
            access: LinuxSandboxMountAccess::ReadOnly,
            layer: 0,
        })
    }

    fn mount_overlay(overlay: &LinuxSandboxOverlay) -> Result<(), String> {
        let target = rooted(&overlay.destination)?;
        ensure_directory_path(&target, "overlay target")?;
        // Open the final mountpoint after every lower layer is present. The
        // retained descriptor, not this pathname, is the destination authority
        // consumed by move_mount below.
        let target_authority = open_mount_target_no_symlinks(&overlay.destination)?;
        let state = inherited_directory(overlay.state_fd, "overlay state")?;
        let upper = state
            .open_child_directory(OsStr::new("upper"))
            .map_err(|error| format!("open overlay upper directory: {error}"))?
            .ok_or_else(|| "overlay upper directory is missing".to_string())?;
        let work = state
            .open_child_directory(OsStr::new("work"))
            .map_err(|error| format!("open overlay work directory: {error}"))?
            .ok_or_else(|| "overlay work directory is missing".to_string())?;
        let upper_fd = upper
            .try_clone_descriptor()
            .map_err(|error| format!("clone overlay upper authority: {error}"))?;
        let work_fd = work
            .try_clone_descriptor()
            .map_err(|error| format!("clone overlay work authority: {error}"))?;
        let options = format!(
            "lowerdir=/proc/self/fd/{},upperdir=/proc/self/fd/{},workdir=/proc/self/fd/{},userxattr",
            overlay.lower_fd,
            upper_fd.as_raw_fd(),
            work_fd.as_raw_fd()
        );
        // Overlay's legacy string-option ABI cannot consume an O_PATH target
        // directly. Build it on a trusted private-root staging point, harden
        // that mount, then move the mount onto the exact no-follow destination
        // descriptor. No untrusted path is resolved after the proof above.
        let staging = PathBuf::from(format!("{ROOT}/.lillux-overlay-staging"));
        // This staging point belongs solely to the fresh private root, never
        // to a source-backed workspace. Create it here, before ordinary mounts
        // are installed; refuse an incumbent instead of adopting its identity.
        mkdir_one(path_string(&staging)?, 0o700)
            .map_err(|error| format!("create private overlay staging target: {error}"))?;
        ensure_directory_path(&staging, "overlay staging target")?;
        mount_raw(
            Some("overlay"),
            path_string(&staging)?,
            Some("overlay"),
            libc::MS_NOSUID | libc::MS_NODEV,
            Some(&options),
        )
        .map_err(|error| format!("mount descriptor-rooted overlay: {error}"))?;
        if let Err(error) = set_mount_attributes(&staging, false, true, true) {
            let _ = unmount_path(&staging);
            return Err(error);
        }
        if let Err(error) = move_path_mount_to_target(&staging, target_authority.as_raw_fd()) {
            let _ = unmount_path(&staging);
            return Err(error);
        }
        let staging_path = c_string(staging.as_os_str(), "overlay staging target")?;
        syscall_zero(
            unsafe { libc::rmdir(staging_path.as_ptr()) },
            "remove overlay staging target",
        )
    }

    fn bind_descriptor_mount(mount: &LinuxSandboxMount) -> Result<(), String> {
        let target = rooted(&mount.destination)?;
        let recursive = match descriptor_kind(mount.source_fd)? {
            DescriptorKind::Directory => {
                ensure_directory_path(&target, "descriptor mount target")?;
                true
            }
            DescriptorKind::Regular | DescriptorKind::UnixSocket => {
                ensure_regular_path(&target, "descriptor mount target")?;
                false
            }
        };
        // This proof runs after every lower layer has been mounted and before
        // any untrusted process exists. The exact descriptor remains live
        // through move_mount, so a mutable source cannot replace a proven path
        // component between inspection and mount attachment.
        let target_authority = open_mount_target_no_symlinks(&mount.destination)?;
        bind_fd_to_mount_target(
            raw_fd(mount.source_fd)?,
            target_authority.as_raw_fd(),
            mount.access == LinuxSandboxMountAccess::ReadOnly,
            recursive,
        )
    }

    fn bind_fd_to_mount_target(
        source_fd: RawFd,
        target_fd: RawFd,
        read_only: bool,
        recursive: bool,
    ) -> Result<(), String> {
        let flags = OPEN_TREE_CLONE
            | OPEN_TREE_CLOEXEC
            | libc::AT_EMPTY_PATH as libc::c_uint
            | if recursive { AT_RECURSIVE } else { 0 };
        let mount_fd =
            unsafe { libc::syscall(libc::SYS_open_tree, source_fd, c"".as_ptr(), flags) } as RawFd;
        if mount_fd < 0 {
            return Err(format!(
                "clone exact descriptor mount: {}",
                std::io::Error::last_os_error()
            ));
        }
        let mount = unsafe { File::from_raw_fd(mount_fd) };
        set_mount_attributes_fd(mount.as_raw_fd(), read_only, true, recursive)?;
        move_detached_mount_to_target(mount.as_raw_fd(), target_fd)
    }

    fn bind_fd_to_path(fd: RawFd, target: &PathBuf, recursive: bool) -> Result<(), String> {
        let source = format!("/proc/self/fd/{fd}");
        mount_raw(
            Some(&source),
            path_string(target)?,
            None,
            libc::MS_BIND | if recursive { libc::MS_REC } else { 0 },
            None,
        )
        .map_err(|error| format!("bind exact descriptor at {}: {error}", target.display()))
    }

    fn set_mount_attributes(
        target: &PathBuf,
        read_only: bool,
        deny_devices: bool,
        recursive: bool,
    ) -> Result<(), String> {
        let path = c_string(target.as_os_str(), "mount-attribute target")?;
        set_mount_attributes_at(
            libc::AT_FDCWD,
            path.as_ptr(),
            read_only,
            deny_devices,
            recursive,
            0,
        )
    }

    fn set_mount_attributes_fd(
        target_fd: RawFd,
        read_only: bool,
        deny_devices: bool,
        recursive: bool,
    ) -> Result<(), String> {
        set_mount_attributes_at(
            target_fd,
            c"".as_ptr(),
            read_only,
            deny_devices,
            recursive,
            libc::AT_EMPTY_PATH as libc::c_uint,
        )
    }

    fn set_mount_attributes_at(
        directory_fd: RawFd,
        path: *const libc::c_char,
        read_only: bool,
        deny_devices: bool,
        recursive: bool,
        flags: libc::c_uint,
    ) -> Result<(), String> {
        let mut attr_set = MOUNT_ATTR_NOSUID;
        if deny_devices {
            attr_set |= MOUNT_ATTR_NODEV;
        }
        if read_only {
            attr_set |= MOUNT_ATTR_RDONLY;
        }
        let attributes = MountAttr {
            attr_set,
            attr_clr: 0,
            propagation: 0,
            userns_fd: 0,
        };
        let result = unsafe {
            libc::syscall(
                libc::SYS_mount_setattr,
                directory_fd,
                path,
                flags | if recursive { AT_RECURSIVE } else { 0 },
                &attributes,
                std::mem::size_of::<MountAttr>(),
            )
        };
        if result == 0 {
            Ok(())
        } else {
            Err(format!(
                "set sandbox mount attributes: {}",
                std::io::Error::last_os_error()
            ))
        }
    }

    fn move_detached_mount_to_target(mount_fd: RawFd, target_fd: RawFd) -> Result<(), String> {
        let result = unsafe {
            libc::syscall(
                libc::SYS_move_mount,
                mount_fd,
                c"".as_ptr(),
                target_fd,
                c"".as_ptr(),
                MOVE_MOUNT_F_EMPTY_PATH | MOVE_MOUNT_T_EMPTY_PATH,
            )
        };
        if result == 0 {
            Ok(())
        } else {
            Err(format!(
                "attach detached mount to exact target: {}",
                std::io::Error::last_os_error()
            ))
        }
    }

    fn move_path_mount_to_target(source: &PathBuf, target_fd: RawFd) -> Result<(), String> {
        let source = c_string(source.as_os_str(), "mount move source")?;
        let result = unsafe {
            libc::syscall(
                libc::SYS_move_mount,
                libc::AT_FDCWD,
                source.as_ptr(),
                target_fd,
                c"".as_ptr(),
                MOVE_MOUNT_T_EMPTY_PATH,
            )
        };
        if result == 0 {
            Ok(())
        } else {
            Err(format!(
                "move mount to exact target: {}",
                std::io::Error::last_os_error()
            ))
        }
    }

    fn unmount_path(path: &PathBuf) -> Result<(), String> {
        let path = c_string(path.as_os_str(), "unmount target")?;
        syscall_zero(
            unsafe { libc::umount2(path.as_ptr(), libc::MNT_DETACH) },
            "detach sandbox staging mount",
        )
    }

    fn pivot_into_private_root() -> Result<(), String> {
        let root = CString::new(ROOT).expect("static root");
        syscall_zero(
            unsafe { libc::chdir(root.as_ptr()) },
            "enter private root mount",
        )?;
        let dot = c".";
        let old = c".lillux-old-root";
        let result = unsafe { libc::syscall(libc::SYS_pivot_root, dot.as_ptr(), old.as_ptr()) };
        if result != 0 {
            return Err(format!(
                "pivot into private sandbox root: {}",
                std::io::Error::last_os_error()
            ));
        }
        syscall_zero(unsafe { libc::chdir(c"/".as_ptr()) }, "enter sandbox root")?;
        syscall_zero(
            unsafe { libc::umount2(c"/.lillux-old-root".as_ptr(), libc::MNT_DETACH) },
            "detach former host root",
        )?;
        syscall_zero(
            unsafe { libc::rmdir(c"/.lillux-old-root".as_ptr()) },
            "remove former-root mountpoint",
        )
    }

    fn probe_isolated_pid_child() -> Result<(), String> {
        let mut report = [0; 2];
        syscall_zero(
            unsafe { libc::pipe2(report.as_mut_ptr(), libc::O_CLOEXEC) },
            "create PID namespace probe report",
        )?;
        let parent_pid = unsafe { libc::getpid() };
        let pid = unsafe { libc::fork() };
        if pid < 0 {
            close_fd(report[0]);
            close_fd(report[1]);
            return Err(format!(
                "fork isolated PID namespace probe: {}",
                std::io::Error::last_os_error()
            ));
        }
        if pid == 0 {
            close_fd(report[0]);
            let result = (|| {
                if unsafe { libc::getpid() } != 1 {
                    return Err("sandbox child is not PID 1 in its isolated namespace".to_string());
                }
                mount_pid_namespace_proc()?;
                pivot_into_private_root()?;
                if std::fs::read_link("/proc/self").map_err(|error| error.to_string())?
                    != PathBuf::from("1")
                    || std::path::Path::new(&format!("/proc/{parent_pid}")).exists()
                    || std::path::Path::new("/proc/sys").exists()
                    || std::path::Path::new("/proc/meminfo").exists()
                {
                    return Err("PID procfs exposes a foreign or non-task surface".to_string());
                }
                let flags = std::fs::OpenOptions::new()
                    .write(true)
                    .open("/proc/self/oom_score_adj");
                if !matches!(flags, Err(ref error) if error.raw_os_error() == Some(libc::EROFS)) {
                    return Err("PID procfs is not read-only".to_string());
                }
                let descendant = unsafe { libc::fork() };
                if descendant < 0 {
                    return Err("fork PID procfs visibility probe failed".to_string());
                }
                if descendant == 0 {
                    let own = unsafe { libc::getpid() }.to_string();
                    let visible = std::fs::read_link("/proc/self").ok() == Some(PathBuf::from(own));
                    unsafe { libc::_exit(if visible { 0 } else { 125 }) };
                }
                let visible = std::path::Path::new(&format!("/proc/{descendant}")).exists();
                let mut status = 0;
                if unsafe { libc::waitpid(descendant, &mut status, 0) } != descendant
                    || !visible
                    || !libc::WIFEXITED(status)
                    || libc::WEXITSTATUS(status) != 0
                {
                    return Err("PID procfs descendant visibility probe failed".to_string());
                }
                syscall_zero(
                    unsafe { libc::prctl(libc::PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) },
                    "set no_new_privs during sandbox probe",
                )?;
                install_confinement_filter(true)
            })();
            match &result {
                Ok(()) => {
                    let _ = write_all_fd(report[1], &[CHILD_READY]);
                }
                Err(error) => {
                    let _ = write_child_error(report[1], error);
                }
            }
            unsafe { libc::_exit(if result.is_ok() { 0 } else { 125 }) };
        }
        close_fd(report[1]);
        let outcome = read_child_ready(report[0]);
        close_fd(report[0]);
        let mut status = 0;
        if unsafe { libc::waitpid(pid, &mut status, 0) } != pid {
            return Err(format!(
                "wait for isolated PID namespace probe: {}",
                std::io::Error::last_os_error()
            ));
        }
        if libc::WIFEXITED(status) && libc::WEXITSTATUS(status) == 0 {
            outcome
        } else {
            Err(format!(
                "isolated PID namespace probe failed: {}",
                outcome
                    .err()
                    .unwrap_or_else(|| "child exited without failure report".to_string())
            ))
        }
    }

    fn spawn_target(request: LinuxSandboxRequest) -> Result<LinuxSandboxProcess, String> {
        let mut ready = [0; 2];
        syscall_zero(
            unsafe { libc::pipe2(ready.as_mut_ptr(), libc::O_CLOEXEC) },
            "create sandbox readiness pipe",
        )?;
        let reserved_target_descriptors = request
            .target_channels
            .iter()
            .map(|(_, target)| raw_fd(*target))
            .collect::<Result<BTreeSet<_>, _>>()?;
        if let Err(error) = relocate_internal_descriptors(
            &mut ready,
            &reserved_target_descriptors,
            "sandbox readiness pipe",
        ) {
            close_fd(ready[0]);
            close_fd(ready[1]);
            return Err(error);
        }
        let pid = unsafe { libc::fork() };
        if pid < 0 {
            close_fd(ready[0]);
            close_fd(ready[1]);
            return Err(format!(
                "fork sandbox target: {}",
                std::io::Error::last_os_error()
            ));
        }
        if pid == 0 {
            close_fd(ready[0]);
            let outcome = child_target_main(&request, ready[1]);
            if let Err(error) = outcome {
                let _ = write_child_error(ready[1], &error);
            }
            unsafe { libc::_exit(125) };
        }
        close_fd(ready[1]);
        let result = read_child_ready(ready[0]);
        close_fd(ready[0]);
        if let Err(error) = result {
            unsafe {
                libc::kill(pid, libc::SIGKILL);
                libc::waitpid(pid, std::ptr::null_mut(), 0);
            }
            return Err(error);
        }
        Ok(LinuxSandboxProcess { pid })
    }

    fn child_target_main(request: &LinuxSandboxRequest, ready_fd: RawFd) -> Result<(), String> {
        if unsafe { libc::getpid() } != 1 {
            return Err("sandbox target is not PID 1 in its isolated namespace".to_string());
        }
        syscall_zero(
            unsafe { libc::prctl(libc::PR_SET_PDEATHSIG, libc::SIGKILL) },
            "bind sandbox target lifetime to adapter",
        )?;
        // An outside-namespace parent appears as PID 0 here, so getppid
        // cannot prove adapter liveness. The exact readiness pipe refuses a
        // missing parent even if it died before PDEATHSIG was installed.
        if request.proc_filesystem == LinuxSandboxProcFilesystem::PidNamespace {
            mount_pid_namespace_proc()?;
        }
        pivot_into_private_root()?;
        let mut mapped_channels = Vec::with_capacity(request.target_channels.len());
        for (source, target) in &request.target_channels {
            let source = raw_fd(*source)?;
            let target = RawFd::try_from(*target)
                .map_err(|_| "target channel descriptor exceeds RawFd".to_string())?;
            if source != target {
                syscall_zero(
                    unsafe { libc::dup3(source, target, 0) },
                    "place sandbox target channel",
                )?;
            }
            mapped_channels.push(target);
        }
        let mut keep = vec![ready_fd];
        keep.extend(
            mapped_channels
                .into_iter()
                .filter(|fd| *fd > libc::STDERR_FILENO),
        );
        if let LinuxSandboxLifecycle::AwaitRelease {
            release_fd,
            release_keepalive_fd,
        } = request.lifecycle
        {
            keep.push(raw_fd(release_fd)?);
            keep.push(raw_fd(release_keepalive_fd)?);
        }
        close_all_except(&keep)?;
        syscall_zero(
            unsafe { libc::prctl(libc::PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) },
            "set no_new_privs for sandbox target",
        )?;
        install_confinement_filter(request.contain_process_group)?;
        write_all_fd(ready_fd, &[CHILD_READY])?;
        if let LinuxSandboxLifecycle::AwaitRelease {
            release_fd,
            release_keepalive_fd,
        } = request.lifecycle
        {
            let mut release = [0_u8; 1];
            let count = loop {
                let count = unsafe {
                    libc::read(
                        raw_fd(release_fd)?,
                        release.as_mut_ptr().cast(),
                        release.len(),
                    )
                };
                if count >= 0 {
                    break count;
                }
                let error = std::io::Error::last_os_error();
                if error.raw_os_error() != Some(libc::EINTR) {
                    return Err(format!("read sandbox release boundary: {error}"));
                }
            };
            if count != 1 || release[0] != 1 {
                return Err("sandbox release boundary closed or carried invalid data".to_string());
            }
            close_fd(raw_fd(release_fd)?);
            close_fd(raw_fd(release_keepalive_fd)?);
        }
        close_fd(ready_fd);
        exec_target(request)
    }

    /// Called only in the actual PID-namespace child before pivot_root. A
    /// parent which merely unshared CLONE_NEWPID still belongs to its old PID
    /// namespace and must never mount this filesystem. Linux's unprivileged
    /// mount visibility check needs the original proc mount still present at
    /// this setup boundary. Immediately pivot/detach the old root afterwards,
    /// before descriptor closure, confinement, readiness or untrusted exec.
    /// No host procfs is bound into the target view.
    fn mount_pid_namespace_proc() -> Result<(), String> {
        if unsafe { libc::getpid() } != 1 {
            return Err("PID procfs must be mounted by the isolated namespace init".to_string());
        }
        let target = CString::new(format!("{ROOT}/proc")).expect("static proc mountpoint");
        syscall_zero(
            unsafe {
                libc::mount(
                    c"proc".as_ptr(),
                    target.as_ptr(),
                    c"proc".as_ptr(),
                    libc::MS_RDONLY | libc::MS_NOSUID | libc::MS_NODEV | libc::MS_NOEXEC,
                    c"subset=pid".as_ptr().cast(),
                )
            },
            "mount isolated PID-only procfs",
        )
    }

    fn exec_target(request: &LinuxSandboxRequest) -> Result<(), String> {
        let executable = c_string(request.executable.as_os_str(), "sandbox executable")?;
        let argv0 = c_string(&request.argv0, "sandbox argv0")?;
        let mut arguments = Vec::with_capacity(request.arguments.len() + 1);
        arguments.push(argv0);
        for argument in &request.arguments {
            arguments.push(c_string(argument, "sandbox argument")?);
        }
        let mut environment = Vec::with_capacity(request.environment.len());
        for (name, value) in &request.environment {
            let mut entry = OsString::from(name);
            entry.push("=");
            entry.push(value);
            environment.push(c_string(&entry, "sandbox environment")?);
        }
        let argv = arguments
            .iter()
            .map(|value| value.as_ptr())
            .chain(std::iter::once(std::ptr::null()))
            .collect::<Vec<_>>();
        let envp = environment
            .iter()
            .map(|value| value.as_ptr())
            .chain(std::iter::once(std::ptr::null()))
            .collect::<Vec<_>>();
        let cwd = c_string(request.cwd.as_os_str(), "sandbox cwd")?;
        syscall_zero(
            unsafe { libc::chdir(cwd.as_ptr()) },
            "enter sandbox target cwd",
        )?;
        unsafe {
            libc::execve(executable.as_ptr(), argv.as_ptr(), envp.as_ptr());
        }
        Err(format!(
            "exec sandbox target {}: {}",
            request.executable.display(),
            std::io::Error::last_os_error()
        ))
    }

    fn install_confinement_filter(contain_process_group: bool) -> Result<(), String> {
        #[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
        {
            let _ = contain_process_group;
            return Err("native sandbox seccomp is unsupported on this architecture".to_string());
        }
        #[cfg(any(target_arch = "x86_64", target_arch = "aarch64"))]
        {
            const BPF_LD_W_ABS: u16 = 0x20;
            const BPF_JMP_JEQ_K: u16 = 0x15;
            const BPF_JMP_JSET_K: u16 = 0x45;
            const BPF_RET_K: u16 = 0x06;
            const SECCOMP_RET_KILL_PROCESS: u32 = 0x8000_0000;
            const SECCOMP_RET_ERRNO: u32 = 0x0005_0000;
            const SECCOMP_RET_ALLOW: u32 = 0x7fff_0000;
            #[cfg(target_arch = "x86_64")]
            const AUDIT_ARCH: u32 = 0xc000_003e;
            #[cfg(target_arch = "aarch64")]
            const AUDIT_ARCH: u32 = 0xc000_00b7;

            let instruction = |code, jt, jf, k| libc::sock_filter { code, jt, jf, k };
            let mut filter = vec![
                instruction(BPF_LD_W_ABS, 0, 0, 4),
                instruction(BPF_JMP_JEQ_K, 1, 0, AUDIT_ARCH),
                instruction(BPF_RET_K, 0, 0, SECCOMP_RET_KILL_PROCESS),
                instruction(BPF_LD_W_ABS, 0, 0, 0),
            ];
            #[cfg(target_arch = "x86_64")]
            filter.extend([
                instruction(BPF_JMP_JSET_K, 0, 1, 0x4000_0000),
                instruction(BPF_RET_K, 0, 0, SECCOMP_RET_ERRNO | libc::ENOSYS as u32),
            ]);
            // The target runs as PID 1 in a fresh PID namespace, so ordinary
            // signal syscalls remain available for its own descendants. Do
            // not blanket-deny kill/tkill/tgkill: Cargo and language runtimes
            // legitimately use them. Namespace translation prevents those
            // PIDs from naming host processes; the filter instead removes
            // namespace/root mutation and cross-process authority-stealing
            // surfaces.
            let denied = [
                libc::SYS_setns,
                libc::SYS_unshare,
                libc::SYS_mount,
                libc::SYS_umount2,
                libc::SYS_pivot_root,
                libc::SYS_chroot,
                libc::SYS_open_by_handle_at,
                libc::SYS_open_tree,
                libc::SYS_move_mount,
                libc::SYS_mount_setattr,
                libc::SYS_fsopen,
                libc::SYS_fsconfig,
                libc::SYS_fsmount,
                libc::SYS_fspick,
                libc::SYS_ptrace,
                libc::SYS_process_vm_readv,
                libc::SYS_process_vm_writev,
                libc::SYS_pidfd_getfd,
                libc::SYS_bpf,
                libc::SYS_perf_event_open,
                libc::SYS_keyctl,
                libc::SYS_add_key,
                libc::SYS_request_key,
                libc::SYS_reboot,
                libc::SYS_init_module,
                libc::SYS_finit_module,
                libc::SYS_delete_module,
                libc::SYS_swapon,
                libc::SYS_swapoff,
                libc::SYS_acct,
            ];
            for syscall in denied {
                filter.push(instruction(BPF_JMP_JEQ_K, 0, 1, syscall as u32));
                filter.push(instruction(
                    BPF_RET_K,
                    0,
                    0,
                    SECCOMP_RET_ERRNO | libc::EPERM as u32,
                ));
            }
            filter.push(instruction(BPF_JMP_JEQ_K, 0, 1, libc::SYS_clone3 as u32));
            filter.push(instruction(
                BPF_RET_K,
                0,
                0,
                SECCOMP_RET_ERRNO | libc::ENOSYS as u32,
            ));
            if contain_process_group {
                for syscall in [libc::SYS_setsid, libc::SYS_setpgid] {
                    filter.push(instruction(BPF_JMP_JEQ_K, 0, 1, syscall as u32));
                    filter.push(instruction(
                        BPF_RET_K,
                        0,
                        0,
                        SECCOMP_RET_ERRNO | libc::EPERM as u32,
                    ));
                }
            }
            filter.extend([
                instruction(BPF_JMP_JEQ_K, 0, 3, libc::SYS_clone as u32),
                instruction(BPF_LD_W_ABS, 0, 0, 16),
                instruction(
                    BPF_JMP_JSET_K,
                    0,
                    1,
                    (libc::CLONE_NEWCGROUP
                        | libc::CLONE_NEWIPC
                        | libc::CLONE_NEWNET
                        | libc::CLONE_NEWNS
                        | libc::CLONE_NEWPID
                        | libc::CLONE_NEWUSER
                        | libc::CLONE_NEWUTS
                        | libc::CLONE_UNTRACED) as u32,
                ),
                instruction(BPF_RET_K, 0, 0, SECCOMP_RET_ERRNO | libc::EPERM as u32),
                instruction(BPF_RET_K, 0, 0, SECCOMP_RET_ALLOW),
            ]);
            let mut program = libc::sock_fprog {
                len: u16::try_from(filter.len())
                    .map_err(|_| "sandbox seccomp program is too large".to_string())?,
                filter: filter.as_mut_ptr(),
            };
            syscall_zero(
                unsafe {
                    libc::prctl(
                        libc::PR_SET_SECCOMP,
                        libc::SECCOMP_MODE_FILTER,
                        &mut program as *mut libc::sock_fprog,
                    )
                },
                "install sandbox seccomp filter",
            )
        }
    }

    pub fn workspace(
        project_fd: u32,
        state_fd: u32,
        operation: LinuxOverlayWorkspaceOperation,
        max_mutations: usize,
    ) -> Result<LinuxOverlayWorkspaceObservation, String> {
        let _project = inherited_directory(project_fd, "overlay project")?;
        let state = inherited_directory(state_fd, "overlay state")?;
        if operation == LinuxOverlayWorkspaceOperation::Destroy {
            // The journal retains this exact backend-state authority until
            // destruction settles. A prior attempt may have removed either
            // child already; absence is completion, never permission to
            // recreate state. Validate the complete remaining layout first.
            let entries = state
                .entries_no_follow_bounded(3)
                .map_err(|error| format!("inventory overlay destruction state: {error}"))?;
            if entries.iter().any(|entry| {
                entry.entry_type != crate::PinnedEntryType::Directory
                    || !matches!(entry.name.to_str(), Some("upper" | "work"))
            }) {
                return Err("overlay destruction state has an invalid layout".to_string());
            }
            for entry in entries {
                let child = state
                    .open_child_directory(&entry.name)
                    .map_err(|error| format!("open overlay destruction child: {error}"))?
                    .ok_or_else(|| "overlay destruction child disappeared".to_string())?;
                child
                    .remove_contents_recursive_bounded(crate::DirectoryTraversalBudget::new(
                        max_mutations.saturating_add(2),
                        256,
                    ))
                    .map_err(|error| {
                        format!("remove overlay {:?} contents: {error:#}", entry.name)
                    })?;
                if !state
                    .remove_empty_child_if_same(&entry.name, &child)
                    .map_err(|error| format!("remove overlay destruction child: {error:#}"))?
                {
                    return Err("overlay destruction child remained non-empty".to_string());
                }
            }
            return Ok(LinuxOverlayWorkspaceObservation {
                project_identity: directory_identity(project_fd)?,
                state_identity: directory_identity(state_fd)?,
                mutation_content_root: None,
                mutations: Vec::new(),
            });
        }
        let upper = match operation {
            LinuxOverlayWorkspaceOperation::Create => state
                .open_or_create_child(OsStr::new("upper"), 0o700)
                .map_err(|error| format!("create overlay upper directory: {error}"))?,
            LinuxOverlayWorkspaceOperation::Observe | LinuxOverlayWorkspaceOperation::Destroy => {
                state
                    .open_child_directory(OsStr::new("upper"))
                    .map_err(|error| format!("open overlay upper directory: {error}"))?
                    .ok_or_else(|| "overlay upper directory is missing".to_string())?
            }
        };
        let _work = match operation {
            LinuxOverlayWorkspaceOperation::Create => state
                .open_or_create_child(OsStr::new("work"), 0o700)
                .map_err(|error| format!("create overlay work directory: {error}"))?,
            LinuxOverlayWorkspaceOperation::Observe | LinuxOverlayWorkspaceOperation::Destroy => {
                state
                    .open_child_directory(OsStr::new("work"))
                    .map_err(|error| format!("open overlay work directory: {error}"))?
                    .ok_or_else(|| "overlay work directory is missing".to_string())?
            }
        };
        let entries = state
            .entries_no_follow_bounded(3)
            .map_err(|error| format!("inventory overlay state: {error}"))?;
        if entries.len() != 2
            || entries.iter().any(|entry| {
                entry.entry_type != crate::PinnedEntryType::Directory
                    || !matches!(entry.name.to_str(), Some("upper" | "work"))
            })
        {
            return Err("overlay state has an invalid layout".to_string());
        }
        let mutations = if operation == LinuxOverlayWorkspaceOperation::Observe {
            let upper = upper
                .try_clone_descriptor()
                .map_err(|error| format!("clone overlay upper directory: {error}"))?;
            scan_overlay_upper(upper.as_raw_fd(), max_mutations)?
        } else {
            Vec::new()
        };
        Ok(LinuxOverlayWorkspaceObservation {
            project_identity: directory_identity(project_fd)?,
            state_identity: directory_identity(state_fd)?,
            mutation_content_root: (operation == LinuxOverlayWorkspaceOperation::Observe)
                .then(|| "upper".to_string()),
            mutations,
        })
    }

    fn inherited_directory(fd: u32, label: &str) -> Result<crate::PinnedDirectory, String> {
        validate_inherited_directory(fd, label)?;
        let duplicate = duplicate_fd(raw_fd(fd)?)?;
        let file = unsafe { File::from_raw_fd(duplicate) };
        crate::PinnedDirectory::from_open_directory(PathBuf::from(format!("<{label}>")), file)
            .map_err(|error| format!("pin inherited {label}: {error}"))
    }

    fn scan_overlay_upper(
        directory_fd: RawFd,
        max_mutations: usize,
    ) -> Result<Vec<LinuxOverlayMutation>, String> {
        let mut mutations = Vec::new();
        scan_overlay_directory(directory_fd, "", &mut mutations, max_mutations)?;
        mutations.sort_by(|left, right| left.path.cmp(&right.path));
        Ok(mutations)
    }

    fn scan_overlay_directory(
        directory_fd: RawFd,
        prefix: &str,
        mutations: &mut Vec<LinuxOverlayMutation>,
        max_mutations: usize,
    ) -> Result<(), String> {
        let directory = inherited_directory(directory_fd as u32, "overlay scan root")?;
        let entries = directory
            .entries_no_follow_bounded(max_mutations.saturating_add(1))
            .map_err(|error| format!("read overlay upper directory: {error}"))?;
        for entry in entries {
            if mutations.len() >= max_mutations {
                return Err(format!("overlay delta exceeds {max_mutations} mutations"));
            }
            let name = entry
                .name
                .into_string()
                .map_err(|_| "overlay mutation path is not UTF-8".to_string())?;
            if matches!(name.as_str(), "." | "..") || name.contains('/') {
                return Err("overlay mutation has an invalid path component".to_string());
            }
            let relative = if prefix.is_empty() {
                name.clone()
            } else {
                format!("{prefix}/{name}")
            };
            let name_c = CString::new(name).map_err(|_| "overlay path contains NUL".to_string())?;
            let mut stat = std::mem::MaybeUninit::<libc::stat>::uninit();
            syscall_zero(
                unsafe {
                    libc::fstatat(
                        directory_fd,
                        name_c.as_ptr(),
                        stat.as_mut_ptr(),
                        libc::AT_SYMLINK_NOFOLLOW,
                    )
                },
                "inspect overlay mutation",
            )?;
            let stat = unsafe { stat.assume_init() };
            let kind = match stat.st_mode & libc::S_IFMT {
                libc::S_IFREG => {
                    let (size, sha256) = hash_regular_at(directory_fd, &name_c, &stat, &relative)?;
                    LinuxOverlayMutationKind::UpsertRegular {
                        normalized_mode: if stat.st_mode & 0o111 != 0 {
                            0o755
                        } else {
                            0o644
                        },
                        size,
                        sha256,
                    }
                }
                libc::S_IFDIR => {
                    let child = unsafe {
                        libc::openat(
                            directory_fd,
                            name_c.as_ptr(),
                            libc::O_RDONLY | libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC,
                        )
                    };
                    if child < 0 {
                        return Err(format!(
                            "open overlay mutation directory {relative}: {}",
                            std::io::Error::last_os_error()
                        ));
                    }
                    let opaque = directory_is_opaque(child)?;
                    mutations.push(LinuxOverlayMutation {
                        path: relative.clone(),
                        kind: if opaque {
                            LinuxOverlayMutationKind::OpaqueDirectory
                        } else {
                            LinuxOverlayMutationKind::EnsureDirectory
                        },
                    });
                    let result = scan_overlay_directory(child, &relative, mutations, max_mutations);
                    close_fd(child);
                    result?;
                    continue;
                }
                libc::S_IFCHR if stat.st_rdev == 0 => LinuxOverlayMutationKind::DeletePath,
                _ => {
                    return Err(format!(
                        "overlay delta contains unsupported entry type at {relative}"
                    ));
                }
            };
            mutations.push(LinuxOverlayMutation {
                path: relative,
                kind,
            });
        }
        Ok(())
    }

    fn hash_regular_at(
        directory_fd: RawFd,
        name: &CStr,
        expected: &libc::stat,
        relative: &str,
    ) -> Result<(u64, String), String> {
        let fd = unsafe {
            libc::openat(
                directory_fd,
                name.as_ptr(),
                libc::O_RDONLY | libc::O_NOFOLLOW | libc::O_CLOEXEC,
            )
        };
        if fd < 0 {
            return Err(format!(
                "open overlay mutation {relative}: {}",
                std::io::Error::last_os_error()
            ));
        }
        let mut file = unsafe { File::from_raw_fd(fd) };
        verify_regular_identity(&file, expected, relative)?;
        let mut digest = Sha256::new();
        let mut total = 0_u64;
        let mut buffer = [0_u8; 128 * 1024];
        loop {
            let read = file
                .read(&mut buffer)
                .map_err(|error| format!("read overlay mutation {relative}: {error}"))?;
            if read == 0 {
                break;
            }
            total = total
                .checked_add(read as u64)
                .ok_or_else(|| "overlay mutation size overflow".to_string())?;
            digest.update(&buffer[..read]);
        }
        let after = verify_regular_identity(&file, expected, relative)?;
        if total != after.st_size as u64 {
            return Err(format!(
                "overlay mutation changed size during scan: {relative}"
            ));
        }
        Ok((total, format!("{:x}", digest.finalize())))
    }

    fn verify_regular_identity(
        file: &File,
        expected: &libc::stat,
        relative: &str,
    ) -> Result<libc::stat, String> {
        let mut observed = std::mem::MaybeUninit::<libc::stat>::uninit();
        syscall_zero(
            unsafe { libc::fstat(file.as_raw_fd(), observed.as_mut_ptr()) },
            "inspect opened overlay mutation",
        )?;
        let observed = unsafe { observed.assume_init() };
        if observed.st_dev != expected.st_dev
            || observed.st_ino != expected.st_ino
            || observed.st_size != expected.st_size
            || observed.st_mode & libc::S_IFMT != libc::S_IFREG
        {
            return Err(format!(
                "overlay mutation changed identity during scan: {relative}"
            ));
        }
        Ok(observed)
    }

    fn directory_is_opaque(fd: RawFd) -> Result<bool, String> {
        for name in [c"trusted.overlay.opaque", c"user.overlay.opaque"] {
            let mut value = [0_u8; 16];
            let read = unsafe {
                libc::fgetxattr(fd, name.as_ptr(), value.as_mut_ptr().cast(), value.len())
            };
            if read > 0 && matches!(value[0], b'y' | b'Y') {
                return Ok(true);
            }
            if read < 0 {
                let error = std::io::Error::last_os_error();
                if !matches!(error.raw_os_error(), Some(code) if code == libc::ENODATA || code == libc::ENOTSUP)
                {
                    return Err(format!("read overlay opaque marker: {error}"));
                }
            }
        }
        Ok(false)
    }

    fn directory_identity(fd: u32) -> Result<String, String> {
        let fd = raw_fd(fd)?;
        let mut stat = std::mem::MaybeUninit::<libc::stat>::uninit();
        syscall_zero(
            unsafe { libc::fstat(fd, stat.as_mut_ptr()) },
            "inspect directory identity",
        )?;
        let stat = unsafe { stat.assume_init() };
        Ok(format!("dev{}-ino{}", stat.st_dev, stat.st_ino))
    }

    pub fn write_descriptor(fd: u32, bytes: &[u8]) -> Result<(), String> {
        if bytes.len() > MAX_CHILD_ERROR_BYTES * 16 {
            return Err("inherited-descriptor payload exceeds Lillux bound".to_string());
        }
        let duplicate = duplicate_fd(raw_fd(fd)?)?;
        let mut file = unsafe { File::from_raw_fd(duplicate) };
        file.write_all(bytes)
            .map_err(|error| format!("write inherited descriptor: {error}"))
    }

    pub fn read_sealed_descriptor(fd: u32, max_bytes: usize) -> Result<Vec<u8>, String> {
        validate_inherited_fd(fd, "sealed input")?;
        let fd = raw_fd(fd)?;
        let required =
            libc::F_SEAL_SEAL | libc::F_SEAL_SHRINK | libc::F_SEAL_GROW | libc::F_SEAL_WRITE;
        let seals = unsafe { libc::fcntl(fd, libc::F_GET_SEALS) };
        if seals < 0 || seals & required != required {
            return Err("inherited input is not sealed against mutation".to_string());
        }
        let duplicate = duplicate_fd(fd)?;
        let mut file = unsafe { File::from_raw_fd(duplicate) };
        let length = file
            .metadata()
            .map_err(|error| format!("inspect sealed input: {error}"))?
            .len();
        if length > max_bytes as u64 {
            return Err(format!("sealed input exceeds {max_bytes} bytes"));
        }
        let mut bytes = Vec::with_capacity(length as usize);
        file.read_to_end(&mut bytes)
            .map_err(|error| format!("read sealed input: {error}"))?;
        if bytes.len() > max_bytes {
            return Err(format!("sealed input exceeds {max_bytes} bytes"));
        }
        Ok(bytes)
    }

    pub fn validate_current_executable(fd: u32) -> Result<(), String> {
        validate_inherited_fd(fd, "adapter executable")?;
        let mut expected = std::mem::MaybeUninit::<libc::stat>::uninit();
        syscall_zero(
            unsafe { libc::fstat(raw_fd(fd)?, expected.as_mut_ptr()) },
            "inspect adapter executable descriptor",
        )?;
        let current = CString::new("/proc/self/exe").expect("static executable path");
        let mut observed = std::mem::MaybeUninit::<libc::stat>::uninit();
        syscall_zero(
            unsafe { libc::stat(current.as_ptr(), observed.as_mut_ptr()) },
            "inspect current adapter executable",
        )?;
        let expected = unsafe { expected.assume_init() };
        let observed = unsafe { observed.assume_init() };
        if expected.st_dev != observed.st_dev
            || expected.st_ino != observed.st_ino
            || expected.st_mode & libc::S_IFMT != libc::S_IFREG
            || observed.st_mode & libc::S_IFMT != libc::S_IFREG
        {
            return Err("adapter descriptor does not identify the current executable".to_string());
        }
        Ok(())
    }

    pub fn validate_connected_unix_stream(fd: u32) -> Result<(), String> {
        validate_inherited_fd(fd, "Unix stream")?;
        let fd = raw_fd(fd)?;
        let mut socket_type: libc::c_int = 0;
        let mut length = std::mem::size_of::<libc::c_int>() as libc::socklen_t;
        syscall_zero(
            unsafe {
                libc::getsockopt(
                    fd,
                    libc::SOL_SOCKET,
                    libc::SO_TYPE,
                    (&mut socket_type as *mut libc::c_int).cast(),
                    &mut length,
                )
            },
            "inspect Unix stream type",
        )?;
        if socket_type != libc::SOCK_STREAM {
            return Err("target channel is not a stream socket".to_string());
        }
        let mut peer = std::mem::MaybeUninit::<libc::sockaddr_storage>::uninit();
        let mut peer_length = std::mem::size_of::<libc::sockaddr_storage>() as libc::socklen_t;
        syscall_zero(
            unsafe { libc::getpeername(fd, peer.as_mut_ptr().cast(), &mut peer_length) },
            "inspect Unix stream peer",
        )?;
        if unsafe { peer.assume_init() }.ss_family as libc::c_int != libc::AF_UNIX {
            return Err("target channel is not an AF_UNIX socket".to_string());
        }
        Ok(())
    }

    pub fn exit_with_status(status: LinuxSandboxExit) -> ! {
        let code = match status {
            LinuxSandboxExit::Code(code) => code.clamp(0, 255),
            LinuxSandboxExit::Signal(signal) => 128_i32.saturating_add(signal).clamp(1, 255),
        };
        unsafe { libc::_exit(code) }
    }

    fn read_child_ready(fd: RawFd) -> Result<(), String> {
        let mut kind = [0_u8; 1];
        read_exact_fd(fd, &mut kind)?;
        match kind[0] {
            CHILD_READY => Ok(()),
            CHILD_ERROR => {
                let mut length = [0_u8; 4];
                read_exact_fd(fd, &mut length)?;
                let length = u32::from_ne_bytes(length) as usize;
                if length > MAX_CHILD_ERROR_BYTES {
                    return Err("sandbox child error exceeds Lillux bound".to_string());
                }
                let mut bytes = vec![0_u8; length];
                read_exact_fd(fd, &mut bytes)?;
                Err(String::from_utf8_lossy(&bytes).into_owned())
            }
            _ => Err("sandbox child emitted an invalid readiness record".to_string()),
        }
    }

    fn write_child_error(fd: RawFd, error: &str) -> Result<(), String> {
        let bytes = error.as_bytes();
        let bytes = &bytes[..bytes.len().min(MAX_CHILD_ERROR_BYTES)];
        write_all_fd(fd, &[CHILD_ERROR])?;
        write_all_fd(fd, &(bytes.len() as u32).to_ne_bytes())?;
        write_all_fd(fd, bytes)
    }

    fn read_exact_fd(fd: RawFd, bytes: &mut [u8]) -> Result<(), String> {
        let mut read = 0;
        while read < bytes.len() {
            let count =
                unsafe { libc::read(fd, bytes[read..].as_mut_ptr().cast(), bytes.len() - read) };
            if count > 0 {
                read += count as usize;
                continue;
            }
            if count == 0 {
                return Err("sandbox child closed readiness boundary".to_string());
            }
            let error = std::io::Error::last_os_error();
            if error.raw_os_error() != Some(libc::EINTR) {
                return Err(format!("read sandbox readiness: {error}"));
            }
        }
        Ok(())
    }

    fn write_all_fd(fd: RawFd, bytes: &[u8]) -> Result<(), String> {
        let mut written = 0;
        while written < bytes.len() {
            let count =
                unsafe { libc::write(fd, bytes[written..].as_ptr().cast(), bytes.len() - written) };
            if count > 0 {
                written += count as usize;
                continue;
            }
            let error = std::io::Error::last_os_error();
            if error.raw_os_error() != Some(libc::EINTR) {
                return Err(format!("write sandbox boundary: {error}"));
            }
        }
        Ok(())
    }

    fn close_all_except(keep: &[RawFd]) -> Result<(), String> {
        let mut keep = keep
            .iter()
            .copied()
            .filter(|fd| *fd > libc::STDERR_FILENO)
            .collect::<Vec<_>>();
        keep.sort_unstable();
        keep.dedup();
        let mut first = 3_u32;
        for fd in keep {
            let fd = u32::try_from(fd).map_err(|_| "negative retained descriptor".to_string())?;
            if first < fd {
                close_range(first, fd - 1)?;
            }
            first = fd.saturating_add(1);
        }
        close_range(first, u32::MAX)
    }

    fn close_range(first: u32, last: u32) -> Result<(), String> {
        if first > last {
            return Ok(());
        }
        let result = unsafe { libc::syscall(libc::SYS_close_range, first, last, 0_u32) };
        if result == 0 {
            Ok(())
        } else {
            Err(format!(
                "close sandbox descriptor range {first}..={last}: {}",
                std::io::Error::last_os_error()
            ))
        }
    }

    fn validate_absolute_path(path: &PathBuf, label: &str) -> Result<(), String> {
        if !path.is_absolute() || path.as_os_str().as_bytes().contains(&0) {
            return Err(format!("{label} must be an absolute NUL-free path"));
        }
        if path.components().any(|component| {
            !matches!(
                component,
                std::path::Component::RootDir | std::path::Component::Normal(_)
            )
        }) {
            return Err(format!("{label} must be lexically normalized"));
        }
        Ok(())
    }

    fn open_mount_target_no_symlinks(destination: &PathBuf) -> Result<File, String> {
        validate_absolute_path(destination, "sandbox mount destination")?;
        let root = CString::new(ROOT).expect("static sandbox root");
        let root_fd = unsafe {
            libc::open(
                root.as_ptr(),
                libc::O_PATH | libc::O_DIRECTORY | libc::O_CLOEXEC | libc::O_NOFOLLOW,
            )
        };
        if root_fd < 0 {
            return Err(format!(
                "open private root for mount-target proof: {}",
                std::io::Error::last_os_error()
            ));
        }
        let root = unsafe { File::from_raw_fd(root_fd) };
        let relative = destination
            .strip_prefix("/")
            .map_err(|_| "sandbox mount destination is not absolute".to_string())?;
        let relative = c_string(relative.as_os_str(), "sandbox mount destination")?;
        let how = OpenHow {
            flags: (libc::O_PATH | libc::O_CLOEXEC | libc::O_NOFOLLOW) as u64,
            mode: 0,
            resolve: RESOLVE_BENEATH | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_SYMLINKS,
        };
        let fd = unsafe {
            libc::syscall(
                libc::SYS_openat2,
                root.as_raw_fd(),
                relative.as_ptr(),
                &how,
                std::mem::size_of::<OpenHow>(),
            )
        } as RawFd;
        if fd < 0 {
            return Err(format!(
                "prove no-follow sandbox mount destination {}: {}",
                destination.display(),
                std::io::Error::last_os_error()
            ));
        }
        // SAFETY: openat2 returned a new uniquely owned descriptor.
        Ok(unsafe { File::from_raw_fd(fd) })
    }

    fn rooted(path: &PathBuf) -> Result<PathBuf, String> {
        validate_absolute_path(path, "sandbox path")?;
        let relative = path
            .strip_prefix("/")
            .map_err(|_| "sandbox path is not absolute".to_string())?;
        Ok(PathBuf::from(ROOT).join(relative))
    }

    fn ensure_directory_path(path: &PathBuf, label: &str) -> Result<(), String> {
        let c_path = c_string(path.as_os_str(), label)?;
        let mut stat = std::mem::MaybeUninit::<libc::stat>::uninit();
        syscall_zero(
            unsafe { libc::lstat(c_path.as_ptr(), stat.as_mut_ptr()) },
            &format!("inspect {label}"),
        )?;
        if unsafe { stat.assume_init() }.st_mode & libc::S_IFMT != libc::S_IFDIR {
            return Err(format!("{label} is not a directory"));
        }
        Ok(())
    }

    fn ensure_regular_path(path: &PathBuf, label: &str) -> Result<(), String> {
        let c_path = c_string(path.as_os_str(), label)?;
        let mut stat = std::mem::MaybeUninit::<libc::stat>::uninit();
        syscall_zero(
            unsafe { libc::lstat(c_path.as_ptr(), stat.as_mut_ptr()) },
            &format!("inspect {label}"),
        )?;
        if unsafe { stat.assume_init() }.st_mode & libc::S_IFMT != libc::S_IFREG {
            return Err(format!("{label} is not a regular file"));
        }
        Ok(())
    }

    fn validate_inherited_fd(fd: u32, label: &str) -> Result<(), String> {
        let fd = raw_fd(fd)?;
        if fd <= libc::STDERR_FILENO || unsafe { libc::fcntl(fd, libc::F_GETFD) } < 0 {
            return Err(format!(
                "{label} descriptor is not a live inherited descriptor"
            ));
        }
        Ok(())
    }

    fn validate_inherited_directory(fd: u32, label: &str) -> Result<(), String> {
        validate_inherited_fd(fd, label)?;
        if descriptor_kind(fd)? != DescriptorKind::Directory {
            return Err(format!("{label} descriptor is not a directory"));
        }
        Ok(())
    }

    fn raw_fd(fd: u32) -> Result<RawFd, String> {
        RawFd::try_from(fd).map_err(|_| format!("descriptor {fd} exceeds RawFd"))
    }

    fn duplicate_fd(fd: RawFd) -> Result<RawFd, String> {
        let duplicate = unsafe { libc::fcntl(fd, libc::F_DUPFD_CLOEXEC, 3) };
        if duplicate < 0 {
            Err(format!(
                "duplicate inherited descriptor {fd}: {}",
                std::io::Error::last_os_error()
            ))
        } else {
            Ok(duplicate)
        }
    }

    /// Move Lillux-private control descriptors away from every exact target
    /// coordinate before fork. Target remapping may deliberately replace fd 0
    /// or any descriptor above stderr; an internal readiness pipe must never
    /// silently occupy one of those signed destinations.
    fn relocate_internal_descriptors(
        descriptors: &mut [RawFd],
        reserved: &BTreeSet<RawFd>,
        label: &str,
    ) -> Result<(), String> {
        for index in 0..descriptors.len() {
            if !reserved.contains(&descriptors[index]) {
                continue;
            }
            let original = descriptors[index];
            let mut occupied_reservations = Vec::new();
            let replacement = loop {
                let candidate =
                    duplicate_fd(original).map_err(|error| format!("relocate {label}: {error}"))?;
                if reserved.contains(&candidate) {
                    // Keep this duplicate open while searching so F_DUPFD
                    // advances past an intentionally reserved target.
                    // SAFETY: `duplicate_fd` returned one newly owned fd.
                    occupied_reservations.push(unsafe { File::from_raw_fd(candidate) });
                    continue;
                }
                break candidate;
            };
            close_fd(original);
            descriptors[index] = replacement;
        }
        Ok(())
    }

    fn mount_raw(
        source: Option<&str>,
        target: &str,
        filesystem: Option<&str>,
        flags: libc::c_ulong,
        data: Option<&str>,
    ) -> std::io::Result<()> {
        let source = source.map(CString::new).transpose().map_err(|_| {
            std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "mount source contains NUL",
            )
        })?;
        let target = CString::new(target).map_err(|_| {
            std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "mount target contains NUL",
            )
        })?;
        let filesystem = filesystem.map(CString::new).transpose().map_err(|_| {
            std::io::Error::new(std::io::ErrorKind::InvalidInput, "filesystem contains NUL")
        })?;
        let data = data.map(CString::new).transpose().map_err(|_| {
            std::io::Error::new(std::io::ErrorKind::InvalidInput, "mount data contains NUL")
        })?;
        let result = unsafe {
            libc::mount(
                source
                    .as_ref()
                    .map_or(std::ptr::null(), |value| value.as_ptr()),
                target.as_ptr(),
                filesystem
                    .as_ref()
                    .map_or(std::ptr::null(), |value| value.as_ptr()),
                flags,
                data.as_ref()
                    .map_or(std::ptr::null(), |value| value.as_ptr().cast()),
            )
        };
        if result == 0 {
            Ok(())
        } else {
            Err(std::io::Error::last_os_error())
        }
    }

    fn c_string(value: &OsStr, label: &str) -> Result<CString, String> {
        CString::new(value.as_bytes()).map_err(|_| format!("{label} contains NUL"))
    }

    fn path_string(path: &std::path::Path) -> Result<&str, String> {
        path.to_str()
            .ok_or_else(|| format!("sandbox path is not UTF-8: {}", path.display()))
    }

    fn syscall_zero(result: libc::c_int, label: &str) -> Result<(), String> {
        if result == 0 {
            Ok(())
        } else {
            Err(format!("{label}: {}", std::io::Error::last_os_error()))
        }
    }

    fn close_fd(fd: RawFd) {
        if fd >= 0 {
            unsafe { libc::close(fd) };
        }
    }

    #[cfg(test)]
    mod namespace_source_tests {
        use super::*;

        #[test]
        fn filesystem_socket_uses_existing_mount_kind_and_exact_identity() {
            let temporary = tempfile::tempdir().unwrap();
            let path = temporary.path().join("callback.sock");
            let _listener = std::os::unix::net::UnixListener::bind(&path).unwrap();
            let original = crate::secure_fs::pin_canonical_mount_source(&path).unwrap();
            assert_eq!(
                descriptor_kind(original.as_raw_fd() as u32).unwrap(),
                DescriptorKind::UnixSocket
            );
            assert!(reanchor_mount_source(original.as_raw_fd()).is_ok());
            std::fs::rename(&path, temporary.path().join("retained.sock")).unwrap();
            let _replacement = std::os::unix::net::UnixListener::bind(&path).unwrap();
            assert!(
                reanchor_mount_source_at(original.as_raw_fd(), &path)
                    .unwrap_err()
                    .contains("changed across namespace")
            );
        }

        #[test]
        fn anonymous_socket_is_not_filesystem_mount_authority() {
            let (socket, _peer) = std::os::unix::net::UnixStream::pair().unwrap();
            assert!(reanchor_mount_source(socket.as_raw_fd()).is_err());
        }

        #[test]
        #[ignore = "requires the supported Linux user/mount/network namespace floor"]
        fn pinned_filesystem_socket_connects_across_namespace_mount() {
            use std::io::{Read as _, Write as _};

            let temporary = tempfile::tempdir().unwrap();
            let path = temporary.path().join("callback.sock");
            let listener = std::os::unix::net::UnixListener::bind(&path).unwrap();
            let original = crate::secure_fs::pin_canonical_mount_source(&path).unwrap();
            let pid = unsafe { libc::fork() };
            assert!(pid >= 0);
            if pid == 0 {
                let result = (|| {
                    enter_namespaces(LinuxSandboxNetwork::Isolated)?;
                    let source = reanchor_mount_source(original.as_raw_fd())?;
                    mount_private_root()?;
                    create_private_tmp()?;
                    let mount = LinuxSandboxMount {
                        source_fd: source.as_raw_fd() as u32,
                        destination: PathBuf::from("/tmp/callback.sock"),
                        access: LinuxSandboxMountAccess::ReadOnly,
                        layer: 0,
                    };
                    let target = rooted(&mount.destination)?;
                    create_target(&target, descriptor_kind(mount.source_fd)?)?;
                    bind_descriptor_mount(&mount)?;
                    std::os::unix::net::UnixStream::connect(target)
                        .and_then(|mut stream| stream.write_all(b"exact socket"))
                        .map_err(|error| error.to_string())
                })();
                unsafe { libc::_exit(if result.is_ok() { 0 } else { 125 }) };
            }
            let mut status = 0;
            assert_eq!(unsafe { libc::waitpid(pid, &mut status, 0) }, pid);
            assert!(libc::WIFEXITED(status));
            assert_eq!(libc::WEXITSTATUS(status), 0);
            listener.set_nonblocking(true).unwrap();
            let (mut connection, _) = listener.accept().unwrap();
            let mut bytes = [0; 12];
            connection.read_exact(&mut bytes).unwrap();
            assert_eq!(&bytes, b"exact socket");
        }

        #[test]
        fn namespace_reanchor_refuses_a_replacement_inode() {
            let temporary = tempfile::tempdir().unwrap();
            let path = temporary.path().join("source");
            std::fs::write(&path, b"admitted").unwrap();
            let original = crate::secure_fs::pin_canonical_mount_source(&path).unwrap();
            assert!(reanchor_mount_source_at(original.as_raw_fd(), &path).is_ok());
            std::fs::rename(&path, temporary.path().join("retained")).unwrap();
            std::fs::write(&path, b"substitute").unwrap();
            assert!(
                reanchor_mount_source_at(original.as_raw_fd(), &path)
                    .unwrap_err()
                    .contains("changed across namespace")
            );
        }

        #[test]
        fn namespace_reanchor_refuses_symlink_substitution() {
            let temporary = tempfile::tempdir().unwrap();
            let path = temporary.path().join("source");
            std::fs::create_dir(&path).unwrap();
            let original = crate::secure_fs::pin_canonical_mount_source(&path).unwrap();
            std::fs::rename(&path, temporary.path().join("retained")).unwrap();
            std::os::unix::fs::symlink("retained", &path).unwrap();
            assert!(reanchor_mount_source_at(original.as_raw_fd(), &path).is_err());
        }

        #[test]
        fn private_mount_copy_refuses_unsealed_source() {
            let temporary = tempfile::tempfile().unwrap();
            let directory = tempfile::tempdir().unwrap();
            let staging = crate::PinnedDirectory::open(directory.path())
                .unwrap()
                .unwrap();
            assert!(!mount_source_is_sealed(temporary.as_raw_fd()).unwrap());
            assert!(
                materialize_sealed_mount_source(temporary.as_raw_fd(), &staging)
                    .unwrap_err()
                    .contains("requires a sealed source")
            );
        }

        #[test]
        fn sealed_source_cannot_gain_a_writable_second_alias() {
            let sealed = crate::sealed_memfd(c"mount-alias-test", b"immutable").unwrap();
            let mut request = super::super::tests::minimal_request();
            request.mounts = vec![
                LinuxSandboxMount {
                    source_fd: sealed.as_raw_fd() as u32,
                    destination: PathBuf::from("/read-only"),
                    access: LinuxSandboxMountAccess::ReadOnly,
                    layer: 0,
                },
                LinuxSandboxMount {
                    source_fd: sealed.as_raw_fd() as u32,
                    destination: PathBuf::from("/writable"),
                    access: LinuxSandboxMountAccess::Writable,
                    layer: 0,
                },
            ];
            assert!(
                reanchor_request_sources(&request)
                    .unwrap_err()
                    .contains("cannot grant writable")
            );
        }

        #[test]
        #[ignore = "requires the supported Linux user/mount/network namespace floor"]
        fn inherited_sources_cross_the_real_namespace_boundary() {
            inspect().unwrap();
        }

        // Invoked only by the isolated test-harness exec below. Ordinary test
        // runs do nothing here; no host executable discovery enters production.
        #[test]
        fn pid_proc_after_exec_target() {
            let Ok(stage) = std::env::var("LILLUX_PROC_EXEC_PROBE") else {
                return;
            };
            let executable = std::env::current_exe().unwrap();
            assert_eq!(executable, PathBuf::from("/probe"));
            assert!(std::fs::File::open(&executable).is_ok());
            assert!(!std::path::Path::new(&format!("/{SEALED_STAGING_NAME}")).exists());
            let write = std::fs::OpenOptions::new()
                .write(true)
                .open(&executable)
                .unwrap_err();
            // Linux may report ETXTBSY before testing mount writeability for
            // the currently executing inode. Verify the mount flag as well.
            assert!(matches!(
                write.raw_os_error(),
                Some(libc::EROFS) | Some(libc::ETXTBSY)
            ));
            let mut filesystem = std::mem::MaybeUninit::<libc::statvfs>::uninit();
            assert_eq!(
                unsafe { libc::statvfs(c"/probe".as_ptr(), filesystem.as_mut_ptr()) },
                0
            );
            assert_ne!(
                unsafe { filesystem.assume_init() }.f_flag & libc::ST_RDONLY,
                0
            );
            assert!(!std::path::Path::new("/.lillux-old-root").exists());
            assert!(!std::path::Path::new("/proc/sys").exists());
            assert!(!std::path::Path::new("/proc/meminfo").exists());
            let authority_fd: RawFd = std::env::var("LILLUX_PROBE_CLOSED_FD")
                .unwrap()
                .parse()
                .unwrap();
            assert_eq!(unsafe { libc::fcntl(authority_fd, libc::F_GETFD) }, -1);
            assert_eq!(
                std::io::Error::last_os_error().raw_os_error(),
                Some(libc::EBADF)
            );
            assert_eq!(
                unsafe {
                    libc::mount(
                        c"proc".as_ptr(),
                        c"/proc".as_ptr(),
                        c"proc".as_ptr(),
                        0,
                        std::ptr::null(),
                    )
                },
                -1
            );
            assert_eq!(
                std::io::Error::last_os_error().raw_os_error(),
                Some(libc::EPERM)
            );
            if stage == "root" {
                assert_eq!(unsafe { libc::getpid() }, 1);
                assert!(
                    std::process::Command::new(executable)
                        .args([
                            "--exact",
                            "sandbox::imp::namespace_source_tests::pid_proc_after_exec_target",
                            "--nocapture"
                        ])
                        .env("LILLUX_PROC_EXEC_PROBE", "child")
                        .status()
                        .unwrap()
                        .success()
                );
            } else {
                assert_eq!(stage, "child");
                assert!(unsafe { libc::getpid() } > 1);
            }
        }

        #[test]
        #[ignore = "executes the test harness in real Linux namespaces"]
        fn pid_proc_supports_exact_realized_and_sealed_executable_after_exec() {
            let executable = std::env::current_exe().unwrap();
            // Test-only inventory of this harness's exact loader/library
            // mappings. No host directory or PATH is exposed to the target.
            let mut libraries = std::fs::read_to_string("/proc/self/maps")
                .unwrap()
                .lines()
                .filter_map(|line| line.split_whitespace().nth(5))
                .filter(|path| path.starts_with('/') && std::path::Path::new(path) != executable)
                .map(PathBuf::from)
                .collect::<BTreeSet<_>>();
            let library_path = std::env::join_paths(
                libraries
                    .iter()
                    .filter_map(|path| path.parent())
                    .collect::<BTreeSet<_>>(),
            )
            .unwrap();
            // The test harness uses the platform ELF interpreter alias,
            // unlike the produced runtime artifact's explicit loader path.
            #[cfg(target_arch = "x86_64")]
            libraries.insert(PathBuf::from("/lib64/ld-linux-x86-64.so.2"));
            #[cfg(target_arch = "aarch64")]
            libraries.insert(PathBuf::from("/lib/ld-linux-aarch64.so.1"));
            for sealed in [false, true] {
                let entry = if sealed {
                    crate::sealed_memfd(c"proc-exec-test", &std::fs::read(&executable).unwrap())
                        .unwrap()
                        .try_clone()
                        .unwrap()
                } else {
                    crate::secure_fs::pin_canonical_mount_source(&executable).unwrap()
                };
                let high = unsafe { libc::fcntl(entry.as_raw_fd(), libc::F_DUPFD_CLOEXEC, 200) };
                assert!(high >= 200);
                let sentinel = unsafe { File::from_raw_fd(high) };
                let retained = libraries
                    .iter()
                    .map(|path| {
                        crate::secure_fs::pin_canonical_mount_source(
                            &std::fs::canonicalize(path).unwrap(),
                        )
                        .unwrap()
                    })
                    .collect::<Vec<_>>();
                let mut request = super::super::tests::minimal_request();
                request.executable = PathBuf::from("/probe");
                request.argv0 = OsString::from("probe");
                request.cwd = PathBuf::from("/");
                request.proc_filesystem = LinuxSandboxProcFilesystem::PidNamespace;
                request.arguments = [
                    "--exact",
                    "sandbox::imp::namespace_source_tests::pid_proc_after_exec_target",
                    "--nocapture",
                ]
                .into_iter()
                .map(OsString::from)
                .collect();
                request.environment = [
                    (OsString::from("LD_LIBRARY_PATH"), library_path.clone()),
                    (
                        OsString::from("LILLUX_PROC_EXEC_PROBE"),
                        OsString::from("root"),
                    ),
                    (
                        OsString::from("LILLUX_PROBE_CLOSED_FD"),
                        OsString::from(sentinel.as_raw_fd().to_string()),
                    ),
                ]
                .into();
                request.mounts = libraries
                    .iter()
                    .zip(&retained)
                    .map(|(path, file)| LinuxSandboxMount {
                        source_fd: file.as_raw_fd() as u32,
                        destination: path.clone(),
                        access: LinuxSandboxMountAccess::ReadOnly,
                        layer: 0,
                    })
                    .collect();
                request.mounts.push(LinuxSandboxMount {
                    source_fd: entry.as_raw_fd() as u32,
                    destination: PathBuf::from("/probe"),
                    access: LinuxSandboxMountAccess::ReadOnly,
                    layer: 0,
                });
                let pid = unsafe { libc::fork() };
                assert!(pid >= 0);
                if pid == 0 {
                    let result = launch(request).and_then(LinuxSandboxProcess::wait);
                    if let Err(error) = &result {
                        eprintln!("proc exec qualification: {error}");
                    }
                    unsafe {
                        libc::_exit(if result == Ok(LinuxSandboxExit::Code(0)) {
                            0
                        } else {
                            125
                        })
                    };
                }
                let mut status = 0;
                assert_eq!(unsafe { libc::waitpid(pid, &mut status, 0) }, pid);
                assert!(libc::WIFEXITED(status));
                assert_eq!(libc::WEXITSTATUS(status), 0, "sealed={sealed}");
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[cfg(target_os = "linux")]
    use std::os::fd::AsRawFd as _;

    pub(super) fn minimal_request() -> LinuxSandboxRequest {
        LinuxSandboxRequest {
            executable: PathBuf::from("/bin/tool"),
            argv0: OsString::from("tool"),
            arguments: Vec::new(),
            cwd: PathBuf::from("/workspace"),
            environment: BTreeMap::new(),
            mounts: Vec::new(),
            fixed_parent_views: Vec::new(),
            overlay: None,
            network: LinuxSandboxNetwork::Isolated,
            private_tmp: true,
            proc_filesystem: LinuxSandboxProcFilesystem::Empty,
            minimal_devices: true,
            target_channels: Vec::new(),
            lifecycle: LinuxSandboxLifecycle::Run,
            contain_process_group: true,
            aggregate_limits: None,
        }
    }

    #[test]
    fn aggregate_limits_are_not_misrepresented_as_rlimits() {
        let mut request = minimal_request();
        request.aggregate_limits = Some(LinuxSandboxAggregateLimits {
            max_processes: Some(32),
            max_memory_bytes: None,
            max_cpu_micros_per_second: None,
        });
        let error = launch_linux_sandbox(request).unwrap_err();
        assert!(error.contains("delegated cgroup-v2 authority"));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn sandbox_paths_reject_parent_components_before_namespace_entry() {
        let mut request = minimal_request();
        request.executable = PathBuf::from("/bin/../secret");
        let error = launch_linux_sandbox(request).unwrap_err();
        assert!(error.contains("lexically normalized"));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn duplicate_mount_destinations_refuse_before_namespace_entry() {
        let mut request = minimal_request();
        request.mounts = vec![
            LinuxSandboxMount {
                source_fd: 999_999,
                destination: PathBuf::from("/tool"),
                access: LinuxSandboxMountAccess::ReadOnly,
                layer: 1,
            },
            LinuxSandboxMount {
                source_fd: 999_999,
                destination: PathBuf::from("/tool"),
                access: LinuxSandboxMountAccess::ReadOnly,
                layer: 2,
            },
        ];
        let error = launch_linux_sandbox(request).unwrap_err();
        assert!(error.contains("live inherited descriptor") || error.contains("unique"));
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn overlay_observation_retains_the_exact_mutation_content_root() {
        let temporary = tempfile::tempdir().unwrap();
        let project_path = temporary.path().join("project");
        let state_path = temporary.path().join("state");
        std::fs::create_dir_all(&project_path).unwrap();
        std::fs::create_dir_all(state_path.join("upper")).unwrap();
        std::fs::create_dir_all(state_path.join("work")).unwrap();
        std::fs::write(state_path.join("upper/result.txt"), b"retained bytes").unwrap();
        let project = crate::PinnedDirectory::open(&project_path)
            .unwrap()
            .unwrap();
        let state = crate::PinnedDirectory::open(&state_path).unwrap().unwrap();
        let project_fd = project.try_clone_descriptor().unwrap();
        let state_fd = state.try_clone_descriptor().unwrap();
        let observation = operate_linux_overlay_workspace(
            project_fd.as_raw_fd() as u32,
            state_fd.as_raw_fd() as u32,
            LinuxOverlayWorkspaceOperation::Observe,
            16,
        )
        .unwrap();
        assert_eq!(observation.mutation_content_root.as_deref(), Some("upper"));
        assert_eq!(observation.mutations.len(), 1);
        assert_eq!(
            std::fs::read(state_path.join("upper/result.txt")).unwrap(),
            b"retained bytes"
        );
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn overlay_destroy_removes_exact_upper_and_work_children() {
        use std::os::unix::fs::PermissionsExt as _;

        let temporary = tempfile::tempdir().unwrap();
        let project_path = temporary.path().join("project");
        let state_path = temporary.path().join("state");
        std::fs::create_dir_all(&project_path).unwrap();
        std::fs::create_dir_all(state_path.join("upper/nested")).unwrap();
        std::fs::create_dir_all(state_path.join("work/work")).unwrap();
        std::fs::set_permissions(
            state_path.join("work/work"),
            std::fs::Permissions::from_mode(0o000),
        )
        .unwrap();
        std::fs::write(state_path.join("upper/nested/result.txt"), b"bytes").unwrap();
        let project = crate::PinnedDirectory::open(&project_path)
            .unwrap()
            .unwrap();
        let state = crate::PinnedDirectory::open(&state_path).unwrap().unwrap();
        let project_fd = project.try_clone_descriptor().unwrap();
        let state_fd = state.try_clone_descriptor().unwrap();
        operate_linux_overlay_workspace(
            project_fd.as_raw_fd() as u32,
            state_fd.as_raw_fd() as u32,
            LinuxOverlayWorkspaceOperation::Destroy,
            16,
        )
        .unwrap();
        assert!(state.entries_no_follow().unwrap().is_empty());
        // The same retained state authority remains valid after a lost
        // success response, with neither child recreated by a retry.
        operate_linux_overlay_workspace(
            project_fd.as_raw_fd() as u32,
            state_fd.as_raw_fd() as u32,
            LinuxOverlayWorkspaceOperation::Destroy,
            16,
        )
        .unwrap();
        assert!(state.entries_no_follow().unwrap().is_empty());
    }

    #[cfg(target_os = "linux")]
    #[test]
    fn overlay_destroy_resumes_partial_removal_but_refuses_foreign_layout() {
        for remaining in ["upper", "work"] {
            let temporary = tempfile::tempdir().unwrap();
            let project_path = temporary.path().join("project");
            let state_path = temporary.path().join("state");
            std::fs::create_dir(&project_path).unwrap();
            std::fs::create_dir_all(state_path.join(remaining)).unwrap();
            std::fs::write(state_path.join(remaining).join("kept"), b"owned").unwrap();
            std::fs::write(state_path.join("unexpected"), b"foreign").unwrap();
            let project = crate::PinnedDirectory::open(&project_path)
                .unwrap()
                .unwrap();
            let state = crate::PinnedDirectory::open(&state_path).unwrap().unwrap();
            let project_fd = project.try_clone_descriptor().unwrap();
            let state_fd = state.try_clone_descriptor().unwrap();
            let destroy = || {
                operate_linux_overlay_workspace(
                    project_fd.as_raw_fd() as u32,
                    state_fd.as_raw_fd() as u32,
                    LinuxOverlayWorkspaceOperation::Destroy,
                    16,
                )
            };
            assert!(destroy().unwrap_err().contains("invalid layout"));
            assert_eq!(
                std::fs::read(state_path.join(remaining).join("kept")).unwrap(),
                b"owned"
            );
            std::fs::remove_file(state_path.join("unexpected")).unwrap();
            destroy().unwrap();
            assert!(state.entries_no_follow().unwrap().is_empty());
        }
    }
}
