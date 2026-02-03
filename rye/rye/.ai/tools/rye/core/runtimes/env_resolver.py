# rye:validated:2026-02-03T01:19:05+00:00:7a2b2e5a5bd3c28c6f670dc177d6a4aafbaa701ee2298232ddc9a0ccaa63d580
"""
Kernel-level environment resolver.

Applies ENV_CONFIG rules from runtimes to produce resolved environment.
All resolution is pure (no side effects, no venv creation).

This follows the extractor pattern: runtimes declare ENV_CONFIG rules,
and the kernel applies them generically using resolver types.
"""

import os
import re
import shutil
import logging
from pathlib import Path
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)


def get_user_space() -> Path:
    """Get the user space directory (~/.ai by default)."""
    return Path.home() / ".ai"


class EnvResolver:
    """
    Generic environment resolver (kernel service).

    Applies ENV_CONFIG rules using resolver types.
    No hardcoded runtime-specific logic.

    Resolver types are internal strategies for finding interpreters:
    - venv_python: Find Python in venv locations
    - node_modules: Find Node in node_modules locations
    - system_binary: Find any binary in system PATH
    - version_manager: Resolve via rbenv, nvm, asdf, etc.
    """

    # Registry of resolver types → method names
    RESOLVER_TYPES = {
        "venv_python": "_resolve_venv_python",
        "node_modules": "_resolve_node_modules",
        "system_binary": "_resolve_system_binary",
        "version_manager": "_resolve_version_manager",
    }

    def __init__(self, project_path: Optional[Path] = None):
        """
        Initialize resolver with project context.

        Args:
            project_path: Path to project root (where .ai/ folder lives)
        """
        self.project_path = Path(project_path) if project_path else None
        self.user_space = get_user_space()
        logger.debug(f"EnvResolver initialized with project_path={self.project_path}")

    def resolve(
        self,
        env_config: Optional[Dict[str, Any]] = None,
        tool_env: Optional[Dict[str, str]] = None,
        include_dotenv: bool = True,
    ) -> Dict[str, str]:
        """
        Resolve environment using ENV_CONFIG rules.

        Args:
            env_config: ENV_CONFIG from runtime (interpreter rules, static env)
            tool_env: Additional env vars from tool CONFIG
            include_dotenv: Whether to load .env files

        Returns:
            Fully resolved environment dict
        """
        env_config = env_config or {}

        # 1. Start with system environment
        env = os.environ.copy()

        # 2. Load .env files
        if include_dotenv:
            dotenv_vars = self._load_dotenv_files()
            env.update(dotenv_vars)

        # 3. Apply interpreter resolution
        interpreter_config = env_config.get("interpreter")
        if interpreter_config:
            resolved_path = self._resolve_interpreter(interpreter_config)
            var_name = interpreter_config.get("var", "INTERPRETER")
            if resolved_path:
                env[var_name] = resolved_path
                logger.debug(f"Resolved {var_name}={resolved_path}")
            elif interpreter_config.get("fallback"):
                env[var_name] = interpreter_config["fallback"]
                logger.debug(f"Using fallback {var_name}={interpreter_config['fallback']}")

        # 4. Apply static env from ENV_CONFIG
        static_env = env_config.get("env", {})
        for key, value in static_env.items():
            env[key] = self._expand_value(value, env)

        # 5. Apply tool-level env overrides
        if tool_env:
            for key, value in tool_env.items():
                env[key] = self._expand_value(str(value), env)

        return env

    def _resolve_interpreter(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Resolve interpreter using the appropriate resolver type.

        Dispatches to resolver method based on config["type"].
        """
        resolver_type = config.get("type")
        if not resolver_type:
            logger.warning("No resolver type specified in interpreter config")
            return None

        method_name = self.RESOLVER_TYPES.get(resolver_type)
        if not method_name:
            # Unknown resolver type - return fallback
            logger.warning(f"Unknown resolver type: {resolver_type}")
            return config.get("fallback")

        method = getattr(self, method_name)
        return method(config)

    def _resolve_venv_python(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Resolve Python from venv locations.

        Search order (configurable via config["search"]):
        - project: {project}/.venv/bin/python
        - rye: {project}/.ai/scripts/.venv/bin/python
        - user: ~/.ai/.venv/bin/python
        - system: which python3 || which python
        """
        search = config.get("search", ["rye", "user", "system"])
        locations = self._build_python_locations()

        for key in search:
            path = locations.get(key)
            if path is None:
                continue
            if isinstance(path, str):
                # System binary path (from which)
                if path:
                    logger.debug(f"Found Python at system: {path}")
                    return path
            elif path.exists():
                logger.debug(f"Found Python at {key}: {path}")
                return str(path)

        fallback = config.get("fallback")
        if fallback:
            logger.debug(f"No Python found in search paths, using fallback: {fallback}")
        return fallback

    def _resolve_node_modules(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Resolve Node from node_modules locations.

        Search order (configurable via config["search"]):
        - project: {project}/node_modules/.bin/node
        - rye: {project}/.ai/scripts/node_modules/.bin/node
        - user: ~/.ai/node_modules/.bin/node
        - system: which node
        """
        search = config.get("search", ["rye", "user", "system"])
        locations = self._build_node_locations()

        for key in search:
            path = locations.get(key)
            if path is None:
                continue
            if isinstance(path, str):
                # System binary path
                if path:
                    logger.debug(f"Found Node at system: {path}")
                    return path
            elif path.exists():
                logger.debug(f"Found Node at {key}: {path}")
                return str(path)

        fallback = config.get("fallback")
        if fallback:
            logger.debug(f"No Node found in search paths, using fallback: {fallback}")
        return fallback

    def _resolve_system_binary(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Resolve binary from system PATH.

        Used for any system-installed binary (deno, ruby, etc.).
        """
        binary = config.get("binary")
        if not binary:
            logger.warning("No binary specified for system_binary resolver")
            return config.get("fallback")

        path = shutil.which(binary)
        if path:
            logger.debug(f"Found {binary} at: {path}")
            return path

        fallback = config.get("fallback")
        if fallback:
            logger.debug(f"Binary {binary} not found, using fallback: {fallback}")
        return fallback

    def _resolve_version_manager(self, config: Dict[str, Any]) -> Optional[str]:
        """
        Resolve via version manager (rbenv, nvm, asdf, etc.).

        Supports:
        - rbenv: Ruby version manager
        - nvm: Node version manager
        - asdf: Universal version manager
        """
        manager = config.get("manager")
        version = config.get("version")
        fallback = config.get("fallback")

        if not manager:
            logger.warning("No manager specified for version_manager resolver")
            return fallback

        if manager == "rbenv":
            return self._resolve_rbenv(version) or fallback
        elif manager == "nvm":
            return self._resolve_nvm(version) or fallback
        elif manager == "asdf":
            return self._resolve_asdf(config.get("plugin"), version) or fallback
        else:
            logger.warning(f"Unknown version manager: {manager}")
            return fallback

    def _build_python_locations(self) -> Dict[str, Any]:
        """
        Build Python search locations based on OS.

        Returns dict with keys: project, rye, user, system
        Values are Path objects or strings (for system).
        """
        # OS-specific paths
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        python_exe = "python.exe" if os.name == "nt" else "python"

        locations = {
            "system": shutil.which("python3") or shutil.which("python"),
            "user": self.user_space / ".venv" / bin_dir / python_exe,
        }

        if self.project_path:
            locations["project"] = self.project_path / ".venv" / bin_dir / python_exe
            locations["rye"] = (
                self.project_path / ".ai" / "scripts" / ".venv" / bin_dir / python_exe
            )

        return locations

    def _build_node_locations(self) -> Dict[str, Any]:
        """
        Build Node search locations based on OS.

        Returns dict with keys: project, rye, user, system
        Values are Path objects or strings (for system).
        """
        # OS-specific paths
        node_exe = "node.exe" if os.name == "nt" else "node"

        locations = {
            "system": shutil.which("node"),
            "user": self.user_space / "node_modules" / ".bin" / node_exe,
        }

        if self.project_path:
            locations["project"] = self.project_path / "node_modules" / ".bin" / node_exe
            locations["rye"] = (
                self.project_path / ".ai" / "scripts" / "node_modules" / ".bin" / node_exe
            )

        return locations

    def _resolve_rbenv(self, version: Optional[str]) -> Optional[str]:
        """
        Resolve Ruby via rbenv.

        Looks in ~/.rbenv/versions/{version}/bin/ruby or falls back to system.
        """
        rbenv_root = Path(os.environ.get("RBENV_ROOT", Path.home() / ".rbenv"))
        if version:
            path = rbenv_root / "versions" / version / "bin" / "ruby"
            if path.exists():
                logger.debug(f"Found Ruby via rbenv: {path}")
                return str(path)

        # Fallback to system ruby
        system_ruby = shutil.which("ruby")
        if system_ruby:
            logger.debug(f"Using system Ruby: {system_ruby}")
        return system_ruby

    def _resolve_nvm(self, version: Optional[str]) -> Optional[str]:
        """
        Resolve Node via nvm.

        Looks in ~/.nvm/versions/node/{version}/bin/node or falls back to system.
        """
        nvm_dir = Path(os.environ.get("NVM_DIR", Path.home() / ".nvm"))
        if version:
            path = nvm_dir / "versions" / "node" / version / "bin" / "node"
            if path.exists():
                logger.debug(f"Found Node via nvm: {path}")
                return str(path)

        # Fallback to system node
        system_node = shutil.which("node")
        if system_node:
            logger.debug(f"Using system Node: {system_node}")
        return system_node

    def _resolve_asdf(self, plugin: Optional[str], version: Optional[str]) -> Optional[str]:
        """
        Resolve via asdf version manager.

        Looks in ~/.asdf/installs/{plugin}/{version}/bin/{plugin}.
        """
        if not plugin:
            logger.warning("No plugin specified for asdf resolver")
            return None

        asdf_dir = Path(os.environ.get("ASDF_DATA_DIR", Path.home() / ".asdf"))
        if version:
            path = asdf_dir / "installs" / plugin / version / "bin" / plugin
            if path.exists():
                logger.debug(f"Found {plugin} via asdf: {path}")
                return str(path)

        # Fallback to system
        system_bin = shutil.which(plugin)
        if system_bin:
            logger.debug(f"Using system {plugin}: {system_bin}")
        return system_bin

    def _expand_value(self, value: str, env: Dict[str, str]) -> str:
        """
        Expand ${VAR} and ${VAR:-default} in value.

        Supports:
        - ${VAR}: Simple variable expansion
        - ${VAR:-default}: Variable with default fallback

        Examples:
        - "${HOME}/bin" -> "/home/user/bin"
        - "${MISSING:-/tmp}" -> "/tmp"
        """
        # Pattern matches ${VAR} or ${VAR:-default}
        pattern = r"\$\{([^}:]+)(?::-([^}]*))?\}"

        def replacer(match):
            var_name = match.group(1)
            default = match.group(2) or ""
            return env.get(var_name, default)

        return re.sub(pattern, replacer, value)

    def _load_dotenv_files(self) -> Dict[str, str]:
        """
        Load .env files from project and user space.

        Precedence (later overrides earlier):
        1. User space: ~/.ai/.env
        2. Project: {project}/.env
        3. Project: {project}/.env.local

        Returns:
            Dict of environment variables from .env files
        """
        env_vars = {}

        # Try to import dotenv, but don't fail if not available
        try:
            from dotenv import dotenv_values
        except ImportError:
            logger.debug("python-dotenv not installed, skipping .env loading")
            return env_vars

        # Load from user space
        user_env = self.user_space / ".env"
        if user_env.exists():
            try:
                user_vars = dotenv_values(user_env)
                env_vars.update(user_vars)
                logger.debug(f"Loaded {len(user_vars)} vars from {user_env}")
            except Exception as e:
                logger.warning(f"Failed to load {user_env}: {e}")

        # Load from project (if available)
        if self.project_path:
            # Check both .ai/.env (rye standard) and root .env files
            env_paths = [
                self.project_path / ".ai" / ".env",  # RYE standard
                self.project_path / ".env",           # Root .env
                self.project_path / ".env.local",     # Local overrides
            ]
            for project_env in env_paths:
                if project_env.exists():
                    try:
                        project_vars = dotenv_values(project_env)
                        env_vars.update(project_vars)
                        logger.debug(f"Loaded {len(project_vars)} vars from {project_env}")
                    except Exception as e:
                        logger.warning(f"Failed to load {project_env}: {e}")

        return env_vars
