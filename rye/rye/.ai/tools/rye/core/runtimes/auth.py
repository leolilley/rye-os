# rye:validated:2026-02-03T01:19:05+00:00:367fd4baca7e950fff0122be538b0231d9f0e77b0ed2992e5272d6ca30f7b27c
"""
Auth runtime shim - re-exports kernel AuthStore.

RYE tools should import from here for consistency.
The actual implementation lives in the kernel: lilux/runtime/auth.py

Usage:
    from ..runtimes.auth import AuthStore, AuthenticationRequired, RefreshError

    auth_store = AuthStore()  # Uses default service_name="lilux"
    token = await auth_store.get_token("rye_registry", scope="registry:write")
"""

# Re-export kernel auth primitives
from lilux.runtime.auth import AuthenticationRequired, AuthStore, RefreshError

__all__ = ["AuthStore", "AuthenticationRequired", "RefreshError"]
