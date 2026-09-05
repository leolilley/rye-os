//! Owner-private local byte-stream endpoints.
//!
//! Higher RyeOS layers name protocol and authority. Lillux alone owns the
//! platform socket, descriptor-inheritance, pathname publication, and exact
//! cleanup mechanics used by a process-local broker.

use std::ffi::{CString, OsStr, OsString};
use std::io::{Read, Write};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result, bail};

use crate::{PinnedDirectory, protect_descriptor_from_exec};

// The most restrictive supported sockaddr_un pathname budget is 104 bytes
// including its trailing NUL. Keep the protocol-owned endpoint comfortably
// within that platform boundary before asking the OS to bind or connect it.
const MAX_ENDPOINT_PATH_BYTES: usize = 103;

/// One connected local byte stream whose descriptor cannot leak across exec.
pub struct LocalDuplexStream {
    #[cfg(unix)]
    stream: std::os::unix::net::UnixStream,
}

impl LocalDuplexStream {
    /// Connect to an endpoint minted by [`OwnerPrivateLocalDuplexListener`].
    pub fn connect(endpoint: &Path) -> Result<Self> {
        validate_endpoint_path(endpoint)?;
        #[cfg(not(unix))]
        {
            let _ = endpoint;
            bail!("local duplex endpoints are unavailable on this platform")
        }
        #[cfg(unix)]
        {
            let stream = std::os::unix::net::UnixStream::connect(endpoint)
                .with_context(|| format!("connect local endpoint {}", endpoint.display()))?;
            protect_descriptor_from_exec(&stream).map_err(anyhow::Error::msg)?;
            Ok(Self { stream })
        }
    }

    /// Connect to the trusted PID-1 broker in the caller's isolated runtime.
    ///
    /// A same-UID descendant can unlink and replace a pathname even below the
    /// private tmpfs. Proving the connected peer is namespace PID 1 prevents
    /// that replacement from impersonating the retained broker listener.
    pub fn connect_isolated_runtime_broker(endpoint: &Path) -> Result<Self> {
        #[cfg(not(target_os = "linux"))]
        {
            let _ = endpoint;
            bail!("isolated local broker connections require Linux SO_PEERCRED")
        }
        #[cfg(target_os = "linux")]
        {
            // SAFETY: getpid has no pointer arguments or caller-owned memory.
            if unsafe { libc::getpid() } <= 1 {
                bail!("isolated local broker client is not a descendant process");
            }
            let connected = Self::connect(endpoint)?;
            let credentials = peer_credentials(&connected.stream)?;
            // SAFETY: geteuid has no pointer arguments or caller-owned memory.
            let client_uid = unsafe { libc::geteuid() };
            if credentials.pid != 1 || credentials.uid != client_uid {
                bail!("local endpoint server is not the isolated runtime broker");
            }
            Ok(connected)
        }
    }

    pub fn try_clone(&self) -> Result<Self> {
        #[cfg(not(unix))]
        bail!("local duplex endpoints are unavailable on this platform");
        #[cfg(unix)]
        {
            let stream = self.stream.try_clone()?;
            protect_descriptor_from_exec(&stream).map_err(anyhow::Error::msg)?;
            Ok(Self { stream })
        }
    }
}

impl Read for LocalDuplexStream {
    fn read(&mut self, buffer: &mut [u8]) -> std::io::Result<usize> {
        #[cfg(not(unix))]
        {
            let _ = buffer;
            Err(std::io::Error::new(
                std::io::ErrorKind::Unsupported,
                "local duplex endpoints are unavailable on this platform",
            ))
        }
        #[cfg(unix)]
        self.stream.read(buffer)
    }
}

impl Write for LocalDuplexStream {
    fn write(&mut self, buffer: &[u8]) -> std::io::Result<usize> {
        #[cfg(not(unix))]
        {
            let _ = buffer;
            Err(std::io::Error::new(
                std::io::ErrorKind::Unsupported,
                "local duplex endpoints are unavailable on this platform",
            ))
        }
        #[cfg(unix)]
        self.stream.write(buffer)
    }

    fn flush(&mut self) -> std::io::Result<()> {
        #[cfg(not(unix))]
        return Err(std::io::Error::new(
            std::io::ErrorKind::Unsupported,
            "local duplex endpoints are unavailable on this platform",
        ));
        #[cfg(unix)]
        self.stream.flush()
    }
}

/// One exact, uniquely named local listener inside a pinned private root.
///
/// The endpoint name is random per worker boot, is never used as daemon
/// authentication, and is removed only if the published directory entry still
/// names the socket inode created here. The retained listener remains the
/// communication authority if an untrusted same-UID workload later unlinks or
/// replaces the pathname; isolated clients additionally prove their connected
/// server is namespace PID 1 before exchanging protocol bytes.
pub struct OwnerPrivateLocalDuplexListener {
    #[cfg(unix)]
    listener: std::os::unix::net::UnixListener,
    endpoint: PathBuf,
    #[cfg(unix)]
    parent: std::fs::File,
    #[cfg(unix)]
    name: OsString,
    #[cfg(unix)]
    device: u64,
    #[cfg(unix)]
    inode: u64,
}

impl OwnerPrivateLocalDuplexListener {
    /// Bind below the sandbox's private tmpfs runtime view.
    ///
    /// This constructor is intentionally unavailable to an ordinary host
    /// process: the trusted sandbox target must be PID 1 in its fresh PID
    /// namespace, and accepted peers must later prove visibility inside that
    /// same namespace. The endpoint therefore never enters a project tree or
    /// a host-visible same-UID directory.
    pub fn bind_isolated_runtime(directory_name: &str, stem: &str) -> Result<Self> {
        require_isolated_runtime_init()?;
        validate_private_directory_name(directory_name)?;
        let tmp = PinnedDirectory::open(Path::new("/tmp"))?
            .ok_or_else(|| anyhow::anyhow!("isolated private tmp is absent"))?;
        let root = tmp.open_or_create_child(OsStr::new(directory_name), 0o700)?;
        root.tighten_owner_private_directory()?;
        Self::bind(&root, stem)
    }

    /// Create a fresh socket below `directory` without replacing any entry.
    /// The caller creates and retains the private directory through Lillux.
    pub fn bind(directory: &PinnedDirectory, stem: &str) -> Result<Self> {
        validate_stem(stem)?;
        directory.ensure_path_binding()?;
        #[cfg(not(unix))]
        {
            let _ = directory;
            bail!("local duplex endpoints are unavailable on this platform")
        }
        #[cfg(unix)]
        {
            use std::os::unix::fs::{FileTypeExt as _, MetadataExt as _};

            let random = crate::crypto::generate_random_bytes::<32>();
            let name = OsString::from(format!("{stem}-{}.sock", &crate::sha256_hex(&random)[..32]));
            let endpoint = directory.path().join(&name);
            validate_endpoint_path(&endpoint)?;
            let listener = std::os::unix::net::UnixListener::bind(&endpoint)
                .with_context(|| format!("bind fresh local endpoint {}", endpoint.display()))?;
            protect_descriptor_from_exec(&listener).map_err(anyhow::Error::msg)?;
            let metadata = std::fs::symlink_metadata(&endpoint)
                .with_context(|| format!("inspect local endpoint {}", endpoint.display()))?;
            if !metadata.file_type().is_socket() {
                bail!("published local endpoint is not a Unix socket");
            }
            directory.ensure_path_binding()?;
            Ok(Self {
                listener,
                endpoint,
                parent: directory.try_clone_descriptor()?,
                name,
                device: metadata.dev(),
                inode: metadata.ino(),
            })
        }
    }

    pub fn endpoint(&self) -> &Path {
        &self.endpoint
    }

    pub fn accept(&self) -> Result<LocalDuplexStream> {
        #[cfg(not(unix))]
        bail!("local duplex endpoints are unavailable on this platform");
        #[cfg(unix)]
        {
            let (stream, _) = self.listener.accept().context("accept local endpoint")?;
            protect_descriptor_from_exec(&stream).map_err(anyhow::Error::msg)?;
            Ok(LocalDuplexStream { stream })
        }
    }

    /// Accept only a descendant visible inside a fresh isolated PID namespace.
    ///
    /// The trusted broker must be namespace PID 1. Linux reports a peer PID
    /// of zero when that peer has no PID mapping in the receiver's namespace;
    /// requiring a nonzero, non-init peer therefore excludes same-UID host
    /// processes that can discover the filesystem pathname. Higher layers do
    /// not inspect raw credentials or infer namespace membership themselves.
    pub fn accept_isolated_descendant(&self) -> Result<LocalDuplexStream> {
        #[cfg(not(target_os = "linux"))]
        bail!("isolated-descendant local endpoints require Linux SO_PEERCRED");
        #[cfg(target_os = "linux")]
        {
            require_isolated_runtime_init()?;
            let (stream, _) = self.listener.accept().context("accept local endpoint")?;
            let credentials = peer_credentials(&stream)?;
            // SAFETY: geteuid has no pointer arguments or caller-owned memory.
            let broker_uid = unsafe { libc::geteuid() };
            if credentials.pid <= 1 || credentials.uid != broker_uid {
                bail!("local endpoint peer is outside the isolated workload process tree");
            }
            protect_descriptor_from_exec(&stream).map_err(anyhow::Error::msg)?;
            Ok(LocalDuplexStream { stream })
        }
    }
}

#[cfg(target_os = "linux")]
fn peer_credentials(stream: &std::os::unix::net::UnixStream) -> Result<libc::ucred> {
    use std::os::fd::AsRawFd as _;

    let mut credentials = std::mem::MaybeUninit::<libc::ucred>::zeroed();
    let mut length = std::mem::size_of::<libc::ucred>() as libc::socklen_t;
    // SAFETY: the connected descriptor is live and the credential
    // buffer/length pointers remain writable for the complete call.
    if unsafe {
        libc::getsockopt(
            stream.as_raw_fd(),
            libc::SOL_SOCKET,
            libc::SO_PEERCRED,
            credentials.as_mut_ptr().cast(),
            &mut length,
        )
    } != 0
    {
        return Err(std::io::Error::last_os_error()).context("read local peer credentials");
    }
    if length as usize != std::mem::size_of::<libc::ucred>() {
        bail!("local peer credentials have an unexpected size");
    }
    // SAFETY: successful getsockopt initialized the full ucred value.
    Ok(unsafe { credentials.assume_init() })
}

fn require_isolated_runtime_init() -> Result<()> {
    #[cfg(not(target_os = "linux"))]
    bail!("isolated local runtime endpoints require Linux PID namespaces");
    #[cfg(target_os = "linux")]
    {
        // SAFETY: getpid has no pointer arguments or caller-owned memory.
        if unsafe { libc::getpid() } != 1 {
            bail!("isolated local broker is not PID 1 in its namespace");
        }
        Ok(())
    }
}

#[cfg(unix)]
impl Drop for OwnerPrivateLocalDuplexListener {
    fn drop(&mut self) {
        use std::os::fd::AsRawFd as _;

        let Ok(name) = os_name_cstring(&self.name) else {
            return;
        };
        let mut observed = std::mem::MaybeUninit::<libc::stat>::zeroed();
        // SAFETY: the parent descriptor and NUL-terminated child name remain
        // live for this call; the output points at writable stat storage.
        if unsafe {
            libc::fstatat(
                self.parent.as_raw_fd(),
                name.as_ptr(),
                observed.as_mut_ptr(),
                libc::AT_SYMLINK_NOFOLLOW,
            )
        } != 0
        {
            return;
        }
        // SAFETY: successful fstatat initialized the complete stat value.
        let observed = unsafe { observed.assume_init() };
        if observed.st_dev as u64 != self.device
            || observed.st_ino as u64 != self.inode
            || observed.st_mode & libc::S_IFMT != libc::S_IFSOCK
        {
            return;
        }
        // SAFETY: exact identity was checked descriptor-relatively above.
        let _ = unsafe { libc::unlinkat(self.parent.as_raw_fd(), name.as_ptr(), 0) };
    }
}

fn validate_stem(stem: &str) -> Result<()> {
    if stem.is_empty()
        || stem.len() > 64
        || !stem
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || byte == b'-')
    {
        bail!("local endpoint stem is not canonical");
    }
    Ok(())
}

fn validate_private_directory_name(name: &str) -> Result<()> {
    if name.is_empty()
        || name.len() > 64
        || name == "."
        || name == ".."
        || !name.bytes().all(|byte| {
            byte.is_ascii_lowercase() || byte.is_ascii_digit() || matches!(byte, b'.' | b'-' | b'_')
        })
    {
        bail!("private local endpoint directory name is not canonical");
    }
    Ok(())
}

fn validate_endpoint_path(endpoint: &Path) -> Result<()> {
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt as _;
        let bytes = endpoint.as_os_str().as_bytes();
        if !endpoint.is_absolute() || bytes.is_empty() || bytes.len() > MAX_ENDPOINT_PATH_BYTES {
            bail!("local endpoint path is not a bounded absolute path");
        }
        if bytes.contains(&0) {
            bail!("local endpoint path contains NUL");
        }
        Ok(())
    }
    #[cfg(not(unix))]
    {
        let _ = endpoint;
        bail!("local duplex endpoints are unavailable on this platform")
    }
}

#[cfg(unix)]
fn os_name_cstring(name: &OsStr) -> Result<CString> {
    use std::os::unix::ffi::OsStrExt as _;
    CString::new(name.as_bytes()).context("local endpoint name contains NUL")
}
