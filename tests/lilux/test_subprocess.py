"""Tests for subprocess primitive (Phase 3.1)."""

import asyncio
from dataclasses import dataclass
import tempfile
from pathlib import Path

import pytest
from lilux.primitives.subprocess import SubprocessResult, SubprocessPrimitive


class TestSubprocessResult:
    """Test SubprocessResult dataclass."""

    def test_create_subprocess_result_success(self):
        """Create successful SubprocessResult."""
        result = SubprocessResult(
            success=True,
            stdout="output",
            stderr="",
            return_code=0,
            duration_ms=100,
        )
        assert result.success is True
        assert result.stdout == "output"
        assert result.stderr == ""
        assert result.return_code == 0
        assert result.duration_ms == 100

    def test_create_subprocess_result_failure(self):
        """Create failed SubprocessResult."""
        result = SubprocessResult(
            success=False,
            stdout="",
            stderr="error",
            return_code=1,
            duration_ms=50,
        )
        assert result.success is False
        assert result.stderr == "error"
        assert result.return_code == 1


@pytest.mark.asyncio
class TestSubprocessPrimitive:
    """Test SubprocessPrimitive execution."""

    async def test_execute_simple_command(self):
        """Execute simple echo command."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "echo",
            "args": ["hello"],
        }
        result = await primitive.execute(config, {})

        assert result.success is True
        assert "hello" in result.stdout
        assert result.return_code == 0
        assert result.duration_ms >= 0

    async def test_execute_command_with_cwd(self):
        """Execute command in specific directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            primitive = SubprocessPrimitive()
            config = {
                "command": "pwd",
                "cwd": tmpdir,
            }
            result = await primitive.execute(config, {})

            assert result.success is True
            assert tmpdir in result.stdout

    async def test_execute_failed_command(self):
        """Capture failed command (non-zero return code)."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "sh",
            "args": ["-c", "exit 42"],
        }
        result = await primitive.execute(config, {})

        assert result.success is False
        assert result.return_code == 42

    async def test_execute_with_input_data(self):
        """Pass input data to command."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "cat",
            "input_data": "test input",
        }
        result = await primitive.execute(config, {})

        assert result.success is True
        assert "test input" in result.stdout

    async def test_env_var_templating_simple(self):
        """Environment variable templating: ${VAR:-default}."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "echo",
            "args": ["${MY_VAR:-default_value}"],
            "env": {"MY_VAR": "custom"},
        }
        result = await primitive.execute(config, {})

        assert result.success is True
        assert "custom" in result.stdout

    async def test_env_var_templating_uses_default(self):
        """Environment variable templating uses default when var missing."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "echo",
            "args": ["${MISSING_VAR:-fallback}"],
            "env": {},
        }
        result = await primitive.execute(config, {})

        assert result.success is True
        assert "fallback" in result.stdout

    async def test_param_templating(self):
        """Runtime parameter templating: {param_name}."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "echo",
            "args": ["parameter is {value}"],
        }
        result = await primitive.execute(config, {"value": "injected"})

        assert result.success is True
        assert "injected" in result.stdout

    async def test_missing_param_left_unchanged(self):
        """Missing parameters are left unchanged in output."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "echo",
            "args": ["{missing_param}"],
        }
        result = await primitive.execute(config, {})

        assert result.success is True
        assert "{missing_param}" in result.stdout

    async def test_both_templating_systems(self):
        """Both env and param templating work together."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "echo",
            "args": ["${VAR1:-default1} {param1}"],
            "env": {"VAR1": "env_value"},
        }
        result = await primitive.execute(config, {"param1": "param_value"})

        assert result.success is True
        assert "env_value" in result.stdout
        assert "param_value" in result.stdout

    async def test_env_merge_small_count(self):
        """Small env count (<50) merges with os.environ."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "sh",
            "args": ["-c", "echo $USER"],
            "env": {"CUSTOM_VAR": "value"},
        }
        # Should merge with os.environ
        result = await primitive.execute(config, {})

        assert result.success is True

    async def test_env_merge_large_count(self):
        """Large env count (>=50) uses directly as resolved env."""
        primitive = SubprocessPrimitive()
        # Create env with >=50 variables
        large_env = {f"VAR_{i}": f"value_{i}" for i in range(50)}
        large_env["CUSTOM_VAR"] = "custom_value"

        config = {
            "command": "echo",
            "args": ["test"],
            "env": large_env,
        }
        result = await primitive.execute(config, {})

        # Should not raise or fail
        assert result.success is True

    async def test_stderr_captured(self):
        """Stderr is captured separately from stdout."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "sh",
            "args": ["-c", "echo stdout_msg && echo stderr_msg >&2"],
        }
        result = await primitive.execute(config, {})

        assert result.success is True
        assert "stdout_msg" in result.stdout
        assert "stderr_msg" in result.stderr

    async def test_duration_ms_populated(self):
        """duration_ms is always populated."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "echo",
            "args": ["test"],
        }
        result = await primitive.execute(config, {})

        assert result.duration_ms is not None
        assert result.duration_ms >= 0

    async def test_command_with_multiple_args(self):
        """Command with multiple arguments."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "echo",
            "args": ["arg1", "arg2", "arg3"],
        }
        result = await primitive.execute(config, {})

        assert result.success is True
        assert "arg1" in result.stdout
        assert "arg2" in result.stdout
        assert "arg3" in result.stdout

    async def test_nonexistent_command_fails(self):
        """Nonexistent command results in failure."""
        primitive = SubprocessPrimitive()
        config = {
            "command": "nonexistent_command_xyz",
        }
        result = await primitive.execute(config, {})

        assert result.success is False
