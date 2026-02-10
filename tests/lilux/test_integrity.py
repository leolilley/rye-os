"""Tests for integrity hashing (Phase 1.2)."""

import json

import pytest

from lilux.primitives.integrity import (
    compute_directive_integrity,
    compute_knowledge_integrity,
    compute_tool_integrity,
)


class TestComputeToolIntegrity:
    """Test compute_tool_integrity(tool_id, version, manifest, files=None)."""

    def test_deterministic_same_input_same_hash(self):
        """Same input produces same hash."""
        manifest = {"name": "test_tool", "inputs": ["param1"]}
        hash1 = compute_tool_integrity("my_tool", "1.0.0", manifest)
        hash2 = compute_tool_integrity("my_tool", "1.0.0", manifest)
        assert hash1 == hash2

    def test_hash_is_64_char_hex(self):
        """Hash is SHA256 hex (64 chars)."""
        manifest = {"name": "test"}
        h = compute_tool_integrity("tool_id", "1.0.0", manifest)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_tool_ids_different_hash(self):
        """Different tool_ids produce different hashes."""
        manifest = {"name": "test"}
        h1 = compute_tool_integrity("tool1", "1.0.0", manifest)
        h2 = compute_tool_integrity("tool2", "1.0.0", manifest)
        assert h1 != h2

    def test_different_versions_different_hash(self):
        """Different versions produce different hashes."""
        manifest = {"name": "test"}
        h1 = compute_tool_integrity("tool_id", "1.0.0", manifest)
        h2 = compute_tool_integrity("tool_id", "1.0.1", manifest)
        assert h1 != h2

    def test_different_manifest_different_hash(self):
        """Different manifest produces different hash."""
        h1 = compute_tool_integrity("tool_id", "1.0.0", {"name": "test"})
        h2 = compute_tool_integrity(
            "tool_id", "1.0.0", {"name": "test", "extra": "field"}
        )
        assert h1 != h2

    def test_with_files_parameter(self):
        """Can optionally include files list."""
        manifest = {"name": "test"}
        files = [{"path": "script.py", "hash": "abc123"}]
        h = compute_tool_integrity("tool_id", "1.0.0", manifest, files=files)
        assert len(h) == 64

    def test_key_order_irrelevant(self):
        """Dict key order doesn't affect hash (canonical JSON)."""
        h1 = compute_tool_integrity("t", "1", {"a": 1, "b": 2})
        h2 = compute_tool_integrity("t", "1", {"b": 2, "a": 1})
        assert h1 == h2

    def test_nested_dict_order_irrelevant(self):
        """Nested dict key order doesn't affect hash."""
        h1 = compute_tool_integrity("t", "1", {"config": {"x": 1, "y": 2}})
        h2 = compute_tool_integrity("t", "1", {"config": {"y": 2, "x": 1}})
        assert h1 == h2


class TestComputeDirectiveIntegrity:
    """Test compute_directive_integrity(directive_name, version, xml_content, metadata=None)."""

    def test_deterministic_directive_hash(self):
        """Same directive input produces same hash."""
        xml = "<directive><name>test</name></directive>"
        h1 = compute_directive_integrity("test_directive", "1.0.0", xml)
        h2 = compute_directive_integrity("test_directive", "1.0.0", xml)
        assert h1 == h2

    def test_directive_hash_is_64_char_hex(self):
        """Directive hash is SHA256 hex (64 chars)."""
        xml = "<directive></directive>"
        h = compute_directive_integrity("dir", "1.0.0", xml)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_directives_different_hash(self):
        """Different directive_names produce different hashes."""
        xml = "<directive></directive>"
        h1 = compute_directive_integrity("dir1", "1.0.0", xml)
        h2 = compute_directive_integrity("dir2", "1.0.0", xml)
        assert h1 != h2

    def test_different_xml_different_hash(self):
        """Different XML content produces different hash."""
        h1 = compute_directive_integrity(
            "dir", "1.0.0", "<directive><step>1</step></directive>"
        )
        h2 = compute_directive_integrity(
            "dir", "1.0.0", "<directive><step>2</step></directive>"
        )
        assert h1 != h2

    def test_with_metadata(self):
        """Can include optional metadata dict."""
        xml = "<directive></directive>"
        metadata = {"author": "test"}
        h = compute_directive_integrity("dir", "1.0.0", xml, metadata=metadata)
        assert len(h) == 64


class TestComputeKnowledgeIntegrity:
    """Test compute_knowledge_integrity(id, version, content, metadata=None)."""

    def test_deterministic_knowledge_hash(self):
        """Same knowledge input produces same hash."""
        content = "This is knowledge"
        h1 = compute_knowledge_integrity("zettel_1", "1.0.0", content)
        h2 = compute_knowledge_integrity("zettel_1", "1.0.0", content)
        assert h1 == h2

    def test_knowledge_hash_is_64_char_hex(self):
        """Knowledge hash is SHA256 hex (64 chars)."""
        h = compute_knowledge_integrity("id", "1.0.0", "content")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_different_ids_different_hash(self):
        """Different IDs produce different hashes."""
        content = "knowledge"
        h1 = compute_knowledge_integrity("id1", "1.0.0", content)
        h2 = compute_knowledge_integrity("id2", "1.0.0", content)
        assert h1 != h2

    def test_different_content_different_hash(self):
        """Different content produces different hash."""
        h1 = compute_knowledge_integrity("id", "1.0.0", "content1")
        h2 = compute_knowledge_integrity("id", "1.0.0", "content2")
        assert h1 != h2

    def test_with_metadata(self):
        """Can include optional metadata dict."""
        content = "knowledge"
        metadata = {"author": "test"}
        h = compute_knowledge_integrity("id", "1.0.0", content, metadata=metadata)
        assert len(h) == 64


class TestIntegrityEdgeCases:
    """Edge cases and integration."""

    def test_empty_manifest(self):
        """Empty manifest produces valid hash."""
        h = compute_tool_integrity("t", "1", {})
        assert len(h) == 64

    def test_none_in_manifest(self):
        """None values in manifest are handled."""
        h = compute_tool_integrity("t", "1", {"key": None})
        assert len(h) == 64

    def test_lists_in_manifest(self):
        """Lists in manifest are handled."""
        h = compute_tool_integrity("t", "1", {"items": [1, 2, 3]})
        assert len(h) == 64

    def test_complex_nested_structure(self):
        """Complex nested structures are deterministic."""
        data = {
            "config": {
                "env": {"VAR1": "val1", "VAR2": "val2"},
                "args": [1, 2, 3],
            },
            "metadata": {"author": "test", "tags": ["a", "b"]},
        }
        h1 = compute_tool_integrity("t", "1", data)
        h2 = compute_tool_integrity("t", "1", data)
        assert h1 == h2
