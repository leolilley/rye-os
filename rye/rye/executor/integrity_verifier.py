"""IntegrityVerifier - Verifies content integrity with caching.

Uses Lilux integrity primitives for hash computation.
Caches verification results for performance.
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from lilux.primitives.integrity import (
    compute_tool_integrity,
    compute_directive_integrity,
    compute_knowledge_integrity,
)

from rye.constants import ItemType

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Result of integrity verification."""

    valid: bool
    expected_hash: Optional[str] = None
    actual_hash: Optional[str] = None
    error: Optional[str] = None
    cached: bool = False


@dataclass
class CacheEntry:
    """Cache entry for verification result."""

    result: VerificationResult
    mtime: float
    size: int
    timestamp: float = field(default_factory=time.time)


class IntegrityVerifier:
    """Verifies content integrity with result caching.

    Uses Lilux pure hash functions for computation.
    Caches results keyed by (path, mtime, size).
    """

    def __init__(self, cache_ttl: float = 300.0, max_cache_size: int = 1000):
        """Initialize verifier.

        Args:
            cache_ttl: Cache time-to-live in seconds (default: 5 minutes)
            max_cache_size: Maximum number of cache entries (default: 1000)
        """
        self.cache_ttl = cache_ttl
        self.max_cache_size = max_cache_size
        self._cache: Dict[str, CacheEntry] = {}
        self._metrics = {"hits": 0, "misses": 0, "evictions": 0}

    def verify_tool(
        self,
        path: Path,
        expected_hash: Optional[str] = None,
    ) -> VerificationResult:
        """Verify tool file integrity.

        Args:
            path: Path to tool file
            expected_hash: Expected hash (from signature or manifest)

        Returns:
            VerificationResult with verification details
        """
        # Check cache first
        cached = self._get_cached(path)
        if cached:
            cached.cached = True
            return cached

        try:
            content = path.read_text(encoding="utf-8")
            metadata = self._extract_tool_metadata(content, path)

            actual_hash = compute_tool_integrity(
                tool_id=metadata.get("tool_id", path.stem),
                version=metadata.get("version", "0.0.0"),
                manifest=metadata,
            )

            valid = True
            if expected_hash:
                # Support both full and short hash comparison
                if len(expected_hash) < 64:
                    valid = actual_hash.startswith(expected_hash)
                else:
                    valid = actual_hash == expected_hash

            result = VerificationResult(
                valid=valid,
                expected_hash=expected_hash,
                actual_hash=actual_hash,
            )

            self._cache_result(path, result)
            return result

        except Exception as e:
            return VerificationResult(
                valid=False,
                error=str(e),
            )

    def verify_directive(
        self,
        path: Path,
        expected_hash: Optional[str] = None,
    ) -> VerificationResult:
        """Verify directive file integrity.

        Args:
            path: Path to directive file
            expected_hash: Expected hash

        Returns:
            VerificationResult
        """
        cached = self._get_cached(path)
        if cached:
            cached.cached = True
            return cached

        try:
            content = path.read_text(encoding="utf-8")
            metadata = self._extract_directive_metadata(content)

            actual_hash = compute_directive_integrity(
                directive_name=metadata.get("name", path.stem),
                version=metadata.get("version", "0.0.0"),
                xml_content=content,
                metadata=metadata,
            )

            valid = True
            if expected_hash:
                if len(expected_hash) < 64:
                    valid = actual_hash.startswith(expected_hash)
                else:
                    valid = actual_hash == expected_hash

            result = VerificationResult(
                valid=valid,
                expected_hash=expected_hash,
                actual_hash=actual_hash,
            )

            self._cache_result(path, result)
            return result

        except Exception as e:
            return VerificationResult(
                valid=False,
                error=str(e),
            )

    def verify_knowledge(
        self,
        path: Path,
        expected_hash: Optional[str] = None,
    ) -> VerificationResult:
        """Verify knowledge entry integrity.

        Args:
            path: Path to knowledge file
            expected_hash: Expected hash

        Returns:
            VerificationResult
        """
        cached = self._get_cached(path)
        if cached:
            cached.cached = True
            return cached

        try:
            content = path.read_text(encoding="utf-8")
            metadata = self._extract_knowledge_metadata(content)

            actual_hash = compute_knowledge_integrity(
                id=metadata.get("id", path.stem),
                version=metadata.get("version", "0.0.0"),
                content=content,
                metadata=metadata,
            )

            valid = True
            if expected_hash:
                if len(expected_hash) < 64:
                    valid = actual_hash.startswith(expected_hash)
                else:
                    valid = actual_hash == expected_hash

            result = VerificationResult(
                valid=valid,
                expected_hash=expected_hash,
                actual_hash=actual_hash,
            )

            self._cache_result(path, result)
            return result

        except Exception as e:
            return VerificationResult(
                valid=False,
                error=str(e),
            )

    def compute_hash(self, path: Path, item_type: str = ItemType.TOOL) -> Optional[str]:
        """Compute integrity hash for a file.

        Args:
            path: Path to file
            item_type: "tool", "directive", or "knowledge"

        Returns:
            Hash string or None on error
        """
        if item_type == ItemType.TOOL:
            result = self.verify_tool(path)
        elif item_type == ItemType.DIRECTIVE:
            result = self.verify_directive(path)
        elif item_type == ItemType.KNOWLEDGE:
            result = self.verify_knowledge(path)
        else:
            return None

        return result.actual_hash

    def _get_cached(self, path: Path) -> Optional[VerificationResult]:
        """Get cached verification result if valid."""
        cache_key = str(path)

        if cache_key not in self._cache:
            self._metrics["misses"] += 1
            return None

        entry = self._cache[cache_key]

        # Check TTL
        if time.time() - entry.timestamp > self.cache_ttl:
            del self._cache[cache_key]
            self._metrics["misses"] += 1
            return None

        # Check if file changed (mtime + size)
        try:
            stat = path.stat()
            if stat.st_mtime != entry.mtime or stat.st_size != entry.size:
                del self._cache[cache_key]
                self._metrics["misses"] += 1
                return None
        except OSError:
            del self._cache[cache_key]
            self._metrics["misses"] += 1
            return None

        self._metrics["hits"] += 1
        return entry.result

    def _cache_result(self, path: Path, result: VerificationResult) -> None:
        """Cache verification result with eviction if cache full."""
        # Evict oldest entry if cache is full
        if len(self._cache) >= self.max_cache_size:
            oldest_key = min(
                self._cache.keys(), key=lambda k: self._cache[k].timestamp
            )
            del self._cache[oldest_key]
            self._metrics["evictions"] += 1

        try:
            stat = path.stat()
            self._cache[str(path)] = CacheEntry(
                result=result,
                mtime=stat.st_mtime,
                size=stat.st_size,
            )
        except OSError:
            pass

    def _extract_tool_metadata(self, content: str, path: Path) -> Dict[str, Any]:
        """Extract minimal metadata for hashing."""
        import ast

        metadata = {"tool_id": path.stem}

        try:
            tree = ast.parse(content)
            for node in tree.body:
                if isinstance(node, ast.Assign) and len(node.targets) == 1:
                    target = node.targets[0]
                    if isinstance(target, ast.Name) and isinstance(
                        node.value, ast.Constant
                    ):
                        if target.id == "__version__":
                            metadata["version"] = node.value.value
                        elif target.id == "__tool_type__":
                            metadata["tool_type"] = node.value.value
        except SyntaxError:
            pass

        return metadata

    def _extract_directive_metadata(self, content: str) -> Dict[str, Any]:
        """Extract directive metadata from XML content."""
        import re

        metadata = {}

        # Extract name from <directive name="...">
        name_match = re.search(r'<directive[^>]+name=["\']([^"\']+)["\']', content)
        if name_match:
            metadata["name"] = name_match.group(1)

        # Extract version from <directive ... version="...">
        version_match = re.search(
            r'<directive[^>]+version=["\']([^"\']+)["\']', content
        )
        if version_match:
            metadata["version"] = version_match.group(1)

        return metadata

    def _extract_knowledge_metadata(self, content: str) -> Dict[str, Any]:
        """Extract knowledge metadata from frontmatter."""
        import re

        metadata = {}

        # Check for YAML frontmatter
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if frontmatter_match:
            try:
                import yaml

                fm = yaml.safe_load(frontmatter_match.group(1))
                if isinstance(fm, dict):
                    metadata = fm
            except Exception:
                pass

        return metadata

    def invalidate(self, path: Path) -> None:
        """Invalidate cache for a specific path."""
        cache_key = str(path)
        if cache_key in self._cache:
            del self._cache[cache_key]

    def clear_cache(self) -> None:
        """Clear all cached verification results."""
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring.

        Returns:
            Dict with cache metrics including hit/miss ratio
        """
        total = self._metrics["hits"] + self._metrics["misses"]
        hit_ratio = (
            self._metrics["hits"] / total if total > 0 else 0.0
        )

        return {
            "cache_size": len(self._cache),
            "max_size": self.max_cache_size,
            "hits": self._metrics["hits"],
            "misses": self._metrics["misses"],
            "evictions": self._metrics["evictions"],
            "hit_ratio": hit_ratio,
        }
