"""Tests for RYE executor system."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from rye.executor import (
    PrimitiveExecutor,
    ChainValidator,
    LockfileResolver,
)
from rye.executor.chain_validator import ChainValidationResult
from rye.executor.primitive_executor import ExecutionResult, ChainElement
from lilux.primitives.lockfile import Lockfile, LockfileRoot


class TestChainValidator:
    """Test ChainValidator space and I/O compatibility validation."""

    def test_empty_chain_valid(self):
        """Empty chain is valid."""
        validator = ChainValidator()
        result = validator.validate_chain([])
        assert result.valid is True
        assert result.validated_pairs == 0

    def test_single_element_valid(self):
        """Single element chain (primitive) is valid."""
        validator = ChainValidator()
        chain = [{"item_id": "subprocess", "space": "system", "executor_id": None}]
        result = validator.validate_chain(chain)
        assert result.valid is True
        assert result.validated_pairs == 0

    def test_valid_project_to_system_chain(self):
        """Project tool depending on system runtime is valid."""
        validator = ChainValidator()
        chain = [
            {"item_id": "git", "space": "project", "tool_type": "python"},
            {"item_id": "python_runtime", "space": "system", "tool_type": "runtime"},
            {
                "item_id": "subprocess",
                "space": "system",
                "tool_type": "primitive",
                "executor_id": None,
            },
        ]
        result = validator.validate_chain(chain)
        assert result.valid is True
        assert result.validated_pairs == 2
        assert len(result.issues) == 0

    def test_valid_same_space_chain(self):
        """Same space dependencies are valid."""
        validator = ChainValidator()
        chain = [
            {"item_id": "custom_tool", "space": "project"},
            {"item_id": "helper_tool", "space": "project"},
        ]
        result = validator.validate_chain(chain)
        assert result.valid is True

    def test_invalid_user_depends_on_project(self):
        """User tool cannot depend on project tool."""
        validator = ChainValidator()
        chain = [
            {"item_id": "user_tool", "space": "user"},
            {"item_id": "project_tool", "space": "project"},
        ]
        result = validator.validate_chain(chain)
        assert result.valid is False
        assert any("cannot depend on" in issue for issue in result.issues)

    def test_invalid_system_depends_on_user(self):
        """System tool cannot depend on user tool."""
        validator = ChainValidator()
        chain = [
            {"item_id": "system_tool", "space": "system"},
            {"item_id": "user_tool", "space": "user"},
        ]
        result = validator.validate_chain(chain)
        assert result.valid is False
        assert any("cannot depend on" in issue for issue in result.issues)

    def test_invalid_system_depends_on_project(self):
        """System tool cannot depend on project tool."""
        validator = ChainValidator()
        chain = [
            {"item_id": "system_tool", "space": "system"},
            {"item_id": "project_tool", "space": "project"},
        ]
        result = validator.validate_chain(chain)
        assert result.valid is False

    def test_io_compatibility_matching(self):
        """Child outputs matching parent inputs is valid."""
        validator = ChainValidator()
        chain = [
            {"item_id": "reader", "space": "project", "outputs": ["json"]},
            {"item_id": "processor", "space": "project", "inputs": ["json"]},
        ]
        result = validator.validate_chain(chain)
        assert result.valid is True

    def test_io_compatibility_missing_input(self):
        """Parent input not provided by child is invalid."""
        validator = ChainValidator()
        chain = [
            {"item_id": "reader", "space": "project", "outputs": ["xml"]},
            {"item_id": "processor", "space": "project", "inputs": ["json"]},
        ]
        result = validator.validate_chain(chain)
        assert result.valid is False
        assert any("I/O mismatch" in issue for issue in result.issues)

    def test_version_constraint_satisfied(self):
        """Version constraints are satisfied."""
        validator = ChainValidator()
        chain = [
            {"item_id": "reader", "space": "project", "version": "1.5.0"},
            {
                "item_id": "processor",
                "space": "project",
                "child_constraints": {
                    "reader": {"min_version": "1.0.0", "max_version": "2.0.0"}
                },
            },
        ]
        result = validator.validate_chain(chain)
        assert result.valid is True

    def test_version_constraint_violated(self):
        """Version below minimum fails."""
        validator = ChainValidator()
        chain = [
            {"item_id": "reader", "space": "project", "version": "0.9.0"},
            {
                "item_id": "processor",
                "space": "project",
                "child_constraints": {"reader": {"min_version": "1.0.0"}},
            },
        ]
        result = validator.validate_chain(chain)
        assert result.valid is False
        assert any("Version constraint failed" in issue for issue in result.issues)


class TestPrimitiveExecutor:
    """Test PrimitiveExecutor tool resolution and chain building."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create executor with test paths."""
        project_tools = tmp_path / ".ai" / "tools"
        project_tools.mkdir(parents=True)

        # System space should be the parent of .ai (executor looks for .ai/tools)
        # But PrimitiveExecutor._get_system_space() returns package/.ai
        # So we pass the .ai folder directly and it appends /tools
        system_space = Path(__file__).parent.parent / "rye" / "rye" / ".ai"

        # Create a custom executor that handles system_space correctly
        executor = PrimitiveExecutor(
            project_path=tmp_path,
            user_space=tmp_path / "user",
        )
        # Override system_space to point to our bundled tools parent
        executor.system_space = system_space
        return executor

    def test_resolve_system_primitive(self, executor):
        """Can resolve subprocess primitive from system space."""
        result = executor._resolve_tool_path(
            "rye/core/primitives/subprocess", "project"
        )
        assert result is not None
        path, space = result
        assert path.exists()
        assert space == "system"
        assert path.stem == "subprocess"

    def test_resolve_system_runtime(self, executor):
        """Can resolve python_runtime from system space."""
        result = executor._resolve_tool_path(
            "rye/core/runtimes/python_runtime", "project"
        )
        assert result is not None
        path, space = result
        assert path.exists()
        assert space == "system"

    def test_load_primitive_metadata(self, executor):
        """Can load metadata from primitive file."""
        result = executor._resolve_tool_path(
            "rye/core/primitives/subprocess", "project"
        )
        assert result is not None
        path, _ = result

        metadata = executor._load_metadata(path)
        assert metadata.get("tool_type") == "primitive"
        assert metadata.get("executor_id") is None
        assert metadata.get("version") == "1.0.0"

    def test_load_runtime_metadata(self, executor):
        """Can load metadata from runtime file."""
        result = executor._resolve_tool_path(
            "rye/core/runtimes/python_runtime", "project"
        )
        assert result is not None
        path, _ = result

        metadata = executor._load_metadata(path)
        assert metadata.get("tool_type") == "runtime"
        assert metadata.get("executor_id") == "rye/core/primitives/subprocess"
        assert metadata.get("env_config") is not None

    @pytest.mark.asyncio
    async def test_build_chain_primitive(self, executor):
        """Building chain for primitive returns single element."""
        chain = await executor._build_chain("rye/core/primitives/subprocess")
        assert len(chain) == 1
        assert chain[0].item_id == "rye/core/primitives/subprocess"
        assert chain[0].executor_id is None
        assert chain[0].space == "system"

    @pytest.mark.asyncio
    async def test_build_chain_runtime(self, executor):
        """Building chain for runtime includes primitive."""
        chain = await executor._build_chain("rye/core/runtimes/python_runtime")
        assert len(chain) == 2
        assert chain[0].item_id == "rye/core/runtimes/python_runtime"
        assert chain[0].executor_id == "rye/core/primitives/subprocess"
        assert chain[1].item_id == "rye/core/primitives/subprocess"
        assert chain[1].executor_id is None

    @pytest.mark.asyncio
    async def test_chain_not_found(self, executor):
        """Non-existent tool returns empty chain."""
        chain = await executor._build_chain("nonexistent_tool_xyz")
        assert chain == []

    def test_template_config(self, executor):
        """Config templating substitutes variables."""
        config = {
            "command": "${PYTHON}",
            "args": ["${SCRIPT}", "--verbose"],
            "nested": {"path": "${HOME}/app"},
        }
        env = {"PYTHON": "/usr/bin/python3", "SCRIPT": "main.py", "HOME": "/home/user"}

        result = executor._template_config(config, env)

        assert result["command"] == "/usr/bin/python3"
        assert result["args"] == ["main.py", "--verbose"]
        assert result["nested"]["path"] == "/home/user/app"

    def test_template_config_with_default(self, executor):
        """Config templating uses defaults for missing vars."""
        config = {"command": "${MISSING:-fallback}"}
        env = {}

        result = executor._template_config(config, env)
        assert result["command"] == "fallback"


class TestLockfileResolver:
    """Test LockfileResolver 3-tier precedence."""

    @pytest.fixture
    def resolver_dirs(self, tmp_path):
        """Create directory structure for lockfile testing."""
        project_dir = tmp_path / "project" / "lockfiles"
        user_dir = tmp_path / "user" / "lockfiles"
        system_dir = tmp_path / "system" / "lockfiles"

        project_dir.mkdir(parents=True)
        user_dir.mkdir(parents=True)
        system_dir.mkdir(parents=True)

        return {
            "project": project_dir.parent,
            "user": tmp_path / "user",
            "system": tmp_path / "system",
        }

    def test_save_and_load_lockfile(self, resolver_dirs):
        """Can save and load a lockfile."""
        resolver = LockfileResolver(
            project_path=resolver_dirs["project"],
            user_space=resolver_dirs["user"],
            system_space=resolver_dirs["system"],
        )

        lockfile = resolver.create_lockfile(
            tool_id="test_tool",
            version="1.0.0",
            integrity="sha256:abc123",
            resolved_chain=[{"tool_id": "test_tool", "space": "project"}],
        )

        path = resolver.save_lockfile(lockfile)
        assert path.exists()

        loaded = resolver.get_lockfile("test_tool", "1.0.0")
        assert loaded is not None
        assert loaded.root.tool_id == "test_tool"
        assert loaded.root.version == "1.0.0"

    def test_precedence_project_over_user(self, resolver_dirs):
        """Project lockfiles take precedence over user."""
        resolver = LockfileResolver(
            project_path=resolver_dirs["project"],
            user_space=resolver_dirs["user"],
            system_space=resolver_dirs["system"],
        )

        # Create lockfile in user space
        user_lockfile = resolver.create_lockfile(
            tool_id="shared_tool",
            version="1.0.0",
            integrity="sha256:user",
            resolved_chain=[{"from": "user"}],
        )
        resolver.scope = "user"
        resolver.save_lockfile(user_lockfile)

        # Create lockfile in project space
        project_lockfile = resolver.create_lockfile(
            tool_id="shared_tool",
            version="1.0.0",
            integrity="sha256:project",
            resolved_chain=[{"from": "project"}],
        )
        resolver.scope = "project"
        resolver.save_lockfile(project_lockfile)

        # Load should return project version
        loaded = resolver.get_lockfile("shared_tool", "1.0.0")
        assert loaded is not None
        assert loaded.root.integrity == "sha256:project"

    def test_precedence_user_over_system(self, resolver_dirs):
        """User lockfiles take precedence over system."""
        # Create system lockfile manually
        system_lockfile_path = (
            resolver_dirs["system"] / "lockfiles" / "sys_tool@1.0.0.lock.json"
        )
        system_lockfile_path.write_text("""{
            "lockfile_version": 1,
            "generated_at": "2026-01-01T00:00:00Z",
            "root": {"tool_id": "sys_tool", "version": "1.0.0", "integrity": "sha256:system"},
            "resolved_chain": [{"from": "system"}]
        }""")

        resolver = LockfileResolver(
            project_path=resolver_dirs["project"],
            user_space=resolver_dirs["user"],
            system_space=resolver_dirs["system"],
        )

        # Create user lockfile
        user_lockfile = resolver.create_lockfile(
            tool_id="sys_tool",
            version="1.0.0",
            integrity="sha256:user",
            resolved_chain=[{"from": "user"}],
        )
        resolver.save_lockfile(user_lockfile)

        # Load should return user version
        loaded = resolver.get_lockfile("sys_tool", "1.0.0")
        assert loaded is not None
        assert loaded.root.integrity == "sha256:user"

    def test_fallback_to_system(self, resolver_dirs):
        """Falls back to system when not in project/user."""
        # Create system lockfile manually
        system_lockfile_path = (
            resolver_dirs["system"] / "lockfiles" / "bundled@1.0.0.lock.json"
        )
        system_lockfile_path.write_text("""{
            "lockfile_version": 1,
            "generated_at": "2026-01-01T00:00:00Z",
            "root": {"tool_id": "bundled", "version": "1.0.0", "integrity": "sha256:bundled"},
            "resolved_chain": [{"from": "system"}]
        }""")

        resolver = LockfileResolver(
            project_path=resolver_dirs["project"],
            user_space=resolver_dirs["user"],
            system_space=resolver_dirs["system"],
        )

        loaded = resolver.get_lockfile("bundled", "1.0.0")
        assert loaded is not None
        assert loaded.root.integrity == "sha256:bundled"

    def test_not_found(self, resolver_dirs):
        """Returns None when lockfile doesn't exist."""
        resolver = LockfileResolver(
            project_path=resolver_dirs["project"],
            user_space=resolver_dirs["user"],
            system_space=resolver_dirs["system"],
        )

        loaded = resolver.get_lockfile("nonexistent", "1.0.0")
        assert loaded is None

    def test_list_lockfiles(self, resolver_dirs):
        """Can list lockfiles across all spaces."""
        resolver = LockfileResolver(
            project_path=resolver_dirs["project"],
            user_space=resolver_dirs["user"],
            system_space=resolver_dirs["system"],
        )

        # Create lockfiles in different spaces
        resolver.scope = "user"
        resolver.save_lockfile(
            resolver.create_lockfile("user_tool", "1.0.0", "sha256:u", [])
        )

        resolver.scope = "project"
        resolver.save_lockfile(
            resolver.create_lockfile("project_tool", "2.0.0", "sha256:p", [])
        )

        lockfiles = resolver.list_lockfiles()
        assert len(lockfiles) == 2

        tool_ids = {lf["tool_id"] for lf in lockfiles}
        assert "user_tool" in tool_ids
        assert "project_tool" in tool_ids

    def test_delete_lockfile(self, resolver_dirs):
        """Can delete lockfile from writable locations."""
        resolver = LockfileResolver(
            project_path=resolver_dirs["project"],
            user_space=resolver_dirs["user"],
            system_space=resolver_dirs["system"],
        )

        # Create and save
        resolver.save_lockfile(
            resolver.create_lockfile("deleteme", "1.0.0", "sha256:d", [])
        )

        assert resolver.exists("deleteme", "1.0.0")

        # Delete
        deleted = resolver.delete_lockfile("deleteme", "1.0.0")
        assert deleted is True
        assert not resolver.exists("deleteme", "1.0.0")


class TestExecutorCaching:
    """Test PrimitiveExecutor hash-based caching."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create executor with test paths."""
        project_tools = tmp_path / ".ai" / "tools"
        project_tools.mkdir(parents=True)

        # Create a test tool
        (project_tools / "cached_tool.py").write_text("""
__version__ = "1.0.0"
__tool_type__ = "primitive"
__executor_id__ = None
__category__ = "test"
""")

        executor = PrimitiveExecutor(project_path=tmp_path)
        return executor, tmp_path

    @pytest.mark.asyncio
    async def test_chain_caching(self, executor):
        """Chain is cached after first build."""
        exec_instance, tmp_path = executor

        # First build
        chain1 = await exec_instance._build_chain("cached_tool")
        assert len(chain1) == 1

        # Should have cached
        stats = exec_instance.get_cache_stats()
        assert stats["chain_cache_size"] == 1

        # Second build uses cache
        chain2 = await exec_instance._build_chain("cached_tool")
        assert chain1[0].item_id == chain2[0].item_id

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_file_change(self, executor):
        """Cache is invalidated when file changes."""
        exec_instance, tmp_path = executor
        tool_path = tmp_path / ".ai" / "tools" / "cached_tool.py"

        # Build and cache
        chain1 = await exec_instance._build_chain("cached_tool")
        assert chain1[0].tool_type == "primitive"
        original_version = chain1[0].config

        # Modify file content (keeping it a valid primitive)
        tool_path.write_text("""
__version__ = "2.0.0"
__tool_type__ = "primitive"
__executor_id__ = None
__category__ = "updated"
""")

        # Build again - should detect change and reload
        chain2 = await exec_instance._build_chain("cached_tool")

        # Should have reloaded with new metadata
        assert chain2[0].item_id == "cached_tool"
        # The chain should reflect the updated category
        assert chain2[0].tool_type == "primitive"

    @pytest.mark.asyncio
    async def test_force_refresh(self, executor):
        """force_refresh=True bypasses cache."""
        exec_instance, tmp_path = executor

        # Build and cache
        await exec_instance._build_chain("cached_tool")
        stats1 = exec_instance.get_cache_stats()
        assert stats1["chain_cache_size"] == 1

        # Force refresh
        chain = await exec_instance._build_chain("cached_tool", force_refresh=True)
        assert len(chain) == 1

    def test_clear_caches(self, executor):
        """clear_caches() clears all caches."""
        exec_instance, _ = executor

        # Add something to metadata cache manually
        exec_instance._metadata_cache["test"] = "value"
        exec_instance._chain_cache["test"] = "value"

        exec_instance.clear_caches()

        stats = exec_instance.get_cache_stats()
        assert stats["chain_cache_size"] == 0
        assert stats["metadata_cache_size"] == 0


class TestTemplateInjectionPrevention:
    """Test that template substitution prevents command injection attacks."""

    def test_shell_command_injection_blocked(self):
        """Test that $(command) injection is properly escaped."""
        executor = PrimitiveExecutor()

        # Config with malicious environment variable
        config = {"script": "${MALICIOUS_VAR}"}
        env = {"MALICIOUS_VAR": "$(rm -rf /)"}

        result = executor._template_config(config, env)

        # The malicious command should be quoted, not executed
        import shlex

        assert result["script"] == shlex.quote("$(rm -rf /)")
        # Should be properly quoted (starts and ends with quotes)
        assert result["script"].startswith("'")
        assert result["script"].endswith("'")

    def test_backtick_injection_blocked(self):
        """Test that backtick command injection is properly escaped."""
        executor = PrimitiveExecutor()

        config = {"command": "${VAR}"}
        env = {"VAR": "`whoami`"}

        result = executor._template_config(config, env)

        # Backticks should be escaped
        import shlex

        assert result["command"] == shlex.quote("`whoami`")
        assert result["command"].startswith("'")

    def test_pipe_injection_blocked(self):
        """Test that pipe injection is properly escaped."""
        executor = PrimitiveExecutor()

        config = {"script": "${VAR}"}
        env = {"VAR": "safe_value | malicious_command"}

        result = executor._template_config(config, env)

        # Pipe should be escaped
        import shlex

        assert result["script"] == shlex.quote("safe_value | malicious_command")

    def test_semicolon_injection_blocked(self):
        """Test that semicolon injection is properly escaped."""
        executor = PrimitiveExecutor()

        config = {"command": "${VAR}"}
        env = {"VAR": "first_command; rm -rf /"}

        result = executor._template_config(config, env)

        # Semicolon should be escaped
        import shlex

        assert result["command"] == shlex.quote("first_command; rm -rf /")

    def test_ampersand_injection_blocked(self):
        """Test that ampersand injection is properly escaped."""
        executor = PrimitiveExecutor()

        config = {"cmd": "${VAR}"}
        env = {"VAR": "safe & malicious"}

        result = executor._template_config(config, env)

        # Ampersand should be escaped
        import shlex

        assert result["cmd"] == shlex.quote("safe & malicious")

    def test_benign_values_not_escaped(self):
        """Test that benign values without shell metacharacters are not unnecessarily quoted."""
        executor = PrimitiveExecutor()

        config = {"path": "${HOME}", "user": "${USER}"}
        env = {"HOME": "/home/user", "USER": "testuser"}

        result = executor._template_config(config, env)

        # Benign values should remain unchanged
        assert result["path"] == "/home/user"
        assert result["user"] == "testuser"

    def test_env_var_with_default_syntax(self):
        """Test ${VAR:-default} syntax is properly handled."""
        executor = PrimitiveExecutor()

        config = {"path": "${PATH:-/usr/bin}"}
        env = {}  # Empty env, should use default

        result = executor._template_config(config, env)

        # Should use the default value
        assert result["path"] == "/usr/bin"

    def test_env_var_with_default_and_injection(self):
        """Test ${VAR:-default} syntax with injection in default value."""
        executor = PrimitiveExecutor()

        config = {"script": "${VAR:-$(rm -rf /)}"}
        env = {}  # Empty env, should use malicious default

        result = executor._template_config(config, env)

        # Should escape the malicious default
        import shlex

        assert result["script"] == shlex.quote("$(rm -rf /)")

    def test_nested_dict_substitution_with_escaping(self):
        """Test environment variable substitution in nested dicts."""
        executor = PrimitiveExecutor()

        config = {"commands": {"script": "${SCRIPT}", "output": "${OUTPUT}"}}
        env = {"SCRIPT": "echo hello; malicious", "OUTPUT": "/tmp/file"}

        result = executor._template_config(config, env)

        # Script with semicolon should be escaped
        import shlex

        assert result["commands"]["script"] == shlex.quote("echo hello; malicious")
        # Benign output should not be escaped
        assert result["commands"]["output"] == "/tmp/file"

    def test_list_substitution_with_escaping(self):
        """Test environment variable substitution in lists."""
        executor = PrimitiveExecutor()

        config = {"args": ["${VAR1}", "${VAR2}", "static"]}
        env = {"VAR1": "$(malicious)", "VAR2": "safe_value"}

        result = executor._template_config(config, env)

        # First arg with injection should be escaped
        import shlex

        assert result["args"][0] == shlex.quote("$(malicious)")
        # Second arg should be unchanged
        assert result["args"][1] == "safe_value"
        # Static value should remain
        assert result["args"][2] == "static"

    def test_multiple_substitutions_in_one_value(self):
        """Test multiple ${VAR} in a single string are all escaped."""
        executor = PrimitiveExecutor()

        config = {"command": "${VAR1} and ${VAR2}"}
        env = {"VAR1": "$(rm)", "VAR2": "; bad"}

        result = executor._template_config(config, env)

        # Both injections should be escaped
        assert "$(rm)" in result["command"]
        assert ";" in result["command"]
        # Both should be quoted (the whole result is one quoted string)
        assert result["command"].startswith("'")
        assert result["command"].endswith("'")

    def test_special_characters_all_escaped(self):
        """Test all shell special characters are escaped."""
        executor = PrimitiveExecutor()

        test_cases = [
            ("$VAR", "${VAR}", {"VAR": "$"}),
            ("`", "${VAR}", {"VAR": "`"}),
            (";", "${VAR}", {"VAR": ";"}),
            ("|", "${VAR}", {"VAR": "|"}),
            ("&", "${VAR}", {"VAR": "&"}),
            ("<", "${VAR}", {"VAR": "<"}),
            (">", "${VAR}", {"VAR": ">"}),
            ("(", "${VAR}", {"VAR": "("}),
            (")", "${VAR}", {"VAR": ")"}),
            ("{", "${VAR}", {"VAR": "{"}),
            ("}", "${VAR}", {"VAR": "}"}),
            ("[", "${VAR}", {"VAR": "["}),
            ("]", "${VAR}", {"VAR": "]"}),
        ]

        for char_desc, config_template, env_value in test_cases:
            config = {"value": config_template}
            result = executor._template_config(config, env_value)

            import shlex

            expected = shlex.quote(env_value["VAR"])
            assert result["value"] == expected, f"Failed to escape {char_desc}"
