"""Authentication store service (Phase 4.2).

Secure credential management using OS keychain integration with
automatic OAuth2 token refresh.
"""

import json
import time
from typing import Any, Dict, List, Optional
import httpx
try:
    import keyring
except ImportError:
    keyring = None

from lilux.primitives.errors import AuthenticationRequired, RefreshError


class AuthStore:
    """Secure credential management using OS keychain."""

    def __init__(self, service_name: str = "lilux"):
        """Initialize auth store with service name.
        
        Args:
            service_name: Service name for keychain storage.
        """
        self.service_name = service_name
        # Cache metadata only (expiry, scopes), not tokens
        self._metadata_cache: Dict[str, Dict[str, Any]] = {}

    def set_token(
        self,
        service: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: int = 3600,
        scopes: Optional[List[str]] = None,
        refresh_config: Optional[Dict[str, str]] = None,
    ) -> None:
        """Store token securely in OS keychain.
        
        Args:
            service: Service identifier.
            access_token: Access token to store.
            refresh_token: Optional refresh token for OAuth2.
            expires_in: Token expiry in seconds from now.
            scopes: Optional list of scopes for this token.
            refresh_config: Optional OAuth2 refresh config (refresh_url, client_id, client_secret).
        """
        # Compute expiry timestamp
        expires_at = time.time() + expires_in

        # Build token data as JSON (so get_token can read all fields)
        token_data = {
            "access_token": access_token,
            "expires_at": expires_at,
            "scopes": scopes or [],
        }
        if refresh_token:
            token_data["refresh_token"] = refresh_token
        if refresh_config:
            token_data["refresh_config"] = refresh_config

        # Store as JSON in keychain
        access_key = f"{self.service_name}_{service}_access_token"
        if keyring:
            try:
                keyring.set_password(self.service_name, access_key, json.dumps(token_data))
            except Exception:
                # Keychain unavailable, continue without storage
                pass

        # Cache metadata (not tokens)
        self._metadata_cache[service] = {
            "expires_at": expires_at,
            "scopes": scopes or [],
        }

    def is_authenticated(self, service: str) -> bool:
        """Check if service has valid authentication.
        
        Args:
            service: Service identifier.
        
        Returns:
            True if token exists for service.
        """
        if not keyring:
            return service in self._metadata_cache
            
        access_key = f"{self.service_name}_{service}_access_token"
        try:
            token = keyring.get_password(self.service_name, access_key)
            return token is not None
        except Exception:
            return False

    def clear_token(self, service: str) -> None:
        """Logout from service (remove token).
        
        Args:
            service: Service identifier.
        """
        if keyring:
            access_key = f"{self.service_name}_{service}_access_token"

            try:
                keyring.delete_password(self.service_name, access_key)
            except Exception:
                pass

        # Clear metadata cache
        self._metadata_cache.pop(service, None)

    async def get_token(
        self,
        service: str,
        scope: Optional[str] = None,
    ) -> str:
        """Retrieve token with automatic refresh on expiry.
        
        Args:
            service: Service identifier.
            scope: Optional scope to validate.
        
        Returns:
            Valid access token.
        
        Raises:
            AuthenticationRequired: If token missing or refresh fails.
        """
        if not keyring:
            raise AuthenticationRequired(f"No token for {service}", service=service)
            
        access_key = f"{self.service_name}_{service}_access_token"

        try:
            # Get token from keychain
            token_json = keyring.get_password(self.service_name, access_key)
        except Exception:
            token_json = None

        if not token_json:
            raise AuthenticationRequired(f"No token for {service}", service=service)

        try:
            token_data = json.loads(token_json)
        except (json.JSONDecodeError, TypeError):
            # Legacy format or invalid JSON
            token_data = {"access_token": token_json}

        # Check expiry
        expires_at = token_data.get("expires_at")
        if expires_at and isinstance(expires_at, (int, float)) and time.time() > expires_at:
            # Token expired - try to refresh
            refresh_token = token_data.get("refresh_token")
            if not refresh_token:
                raise AuthenticationRequired(
                    f"Token expired for {service} and no refresh token",
                    service=service,
                )

            # Refresh token
            try:
                refresh_config = token_data.get("refresh_config") or {}
                refresh_url = refresh_config.get("refresh_url") if isinstance(refresh_config, dict) else None
                client_id = refresh_config.get("client_id") if isinstance(refresh_config, dict) else None
                client_secret = refresh_config.get("client_secret") if isinstance(refresh_config, dict) else None
                
                if not refresh_url or not client_id or not client_secret:
                    raise RefreshError(
                        f"Missing refresh configuration for {service}",
                        service=service,
                    )
                
                new_tokens = await self._refresh_token(
                    refresh_token=str(refresh_token),
                    refresh_url=str(refresh_url),
                    client_id=str(client_id),
                    client_secret=str(client_secret),
                )

                # Update stored token
                current_scopes = token_data.get("scopes")
                self.set_token(
                    service,
                    access_token=new_tokens["access_token"],
                    refresh_token=new_tokens.get("refresh_token"),
                    expires_in=new_tokens.get("expires_in", 3600),
                    scopes=current_scopes if isinstance(current_scopes, list) else None,
                )

                token_data = new_tokens

            except RefreshError:
                raise
            except Exception as e:
                raise RefreshError(
                    f"Failed to refresh token for {service}: {str(e)}",
                    service=service,
                )

        # Check scope if requested
        scopes = token_data.get("scopes", [])
        if scope and scope not in scopes:
            raise AuthenticationRequired(
                f"Token for {service} lacks scope {scope}",
                service=service,
            )

        return token_data["access_token"]

    async def _refresh_token(
        self,
        refresh_token: str,
        refresh_url: str,
        client_id: str,
        client_secret: str,
    ) -> Dict[str, Any]:
        """Refresh OAuth2 token.
        
        Makes HTTP POST to refresh endpoint with OAuth2 credentials.
        
        Args:
            refresh_token: Refresh token value.
            refresh_url: Token refresh endpoint URL.
            client_id: OAuth2 client ID.
            client_secret: OAuth2 client secret.
        
        Returns:
            Dict with new tokens and expiry info.
        
        Raises:
            RefreshError: If refresh fails.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    refresh_url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                        "client_id": client_id,
                        "client_secret": client_secret,
                    },
                    timeout=30,
                )

                if response.status_code != 200:
                    raise RefreshError(
                        f"Refresh failed: {response.status_code} {response.text}"
                    )

                result = response.json()

                return {
                    "access_token": result.get("access_token"),
                    "refresh_token": result.get("refresh_token", refresh_token),
                    "expires_in": result.get("expires_in", 3600),
                }

        except httpx.HTTPError as e:
            raise RefreshError(f"Refresh request failed: {str(e)}")
        except Exception as e:
            raise RefreshError(f"Refresh error: {str(e)}")
