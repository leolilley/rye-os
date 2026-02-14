# rye:signed:2026-02-14T00:37:49Z:ff83a2339367dbb73d04ad85d98761250feffe7a0e267de1af42bd82c135846a:OzHNkjjV5hGYs2tbyMqh5f84GdanH-U2pj3ZQ3ijyYNVdbET1se73B4JVn4K4nSRV3N1bb8Suk2Yw3p0FRTqDg==:440443d0858f0199
"""
Auth runtime shim - re-exports kernel AuthStore.

RYE tools should import from here for consistency.
The actual implementation lives in the kernel: lilux/runtime/auth.py

Usage:
    from ..runtimes.auth import AuthStore, AuthenticationRequired, RefreshError

    auth_store = AuthStore()  # Uses default service_name="lilux"
    token = await auth_store.get_token("rye_registry", scope="registry:write")
"""

__tool_type__ = "python"
__version__ = "1.0.0"
__category__ = "rye/core/runtimes"
__tool_description__ = "Runtime authentication helpers"

# Re-export kernel auth primitives
from lilux.runtime.auth import AuthenticationRequired, AuthStore, RefreshError

__all__ = ["AuthStore", "AuthenticationRequired", "RefreshError"]
