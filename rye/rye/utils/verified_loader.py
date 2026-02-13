"""Language-agnostic signature verification gate for .ai/tools/ dependencies.

Verifies inline Ed25519 signatures before any file under .ai/tools/ is loaded
or executed, regardless of file type. The signature format system (via
MetadataManager → get_signature_format()) is data-driven from the extractor's
SIGNATURE_FORMAT dict — adding a new language just needs a new extractor.

Usage:
    from rye.utils.verified_loader import verify_dependency

    # Verify before loading/executing:
    content_hash = verify_dependency(path, project_path=Path("/my/project"))
"""

import logging
from pathlib import Path
from typing import Optional

from rye.constants import ItemType
from rye.utils.integrity import IntegrityError, verify_item
from rye.utils.path_utils import get_user_space, get_system_space

logger = logging.getLogger(__name__)


def _is_subpath(path: Path, parent: Path) -> bool:
    """Check if path is under parent directory."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _get_allowed_roots(project_path: Optional[Path] = None) -> list:
    """Get allowed root directories for tool loading."""
    roots = []
    if project_path:
        candidate = project_path / ".ai" / "tools"
        if candidate.exists():
            roots.append(candidate.resolve())
    user_tools = get_user_space() / "tools"
    if user_tools.exists():
        roots.append(user_tools.resolve())
    system_tools = get_system_space() / "tools"
    if system_tools.exists():
        roots.append(system_tools.resolve())
    return roots


def verify_dependency(
    path: Path,
    *,
    project_path: Optional[Path] = None,
) -> str:
    """Verify a tool dependency before load/execution.

    Works for any file type that the signature format system supports.
    Calls verify_item() which uses get_signature_format() to find the
    correct comment prefix for the file's extension — data-driven
    from the extractor's SIGNATURE_FORMAT dict.

    Args:
        path: Path to the dependency file (absolute or resolvable).
        project_path: Project root for signature verification context.

    Returns:
        Verified content hash (SHA256 hex digest) on success.

    Raises:
        IntegrityError: On any verification failure (unsigned, tampered,
                        untrusted key, outside allowed roots, symlinked).
        FileNotFoundError: If the file doesn't exist.
    """
    real_path = path.resolve(strict=True)

    # Enforce allowed roots
    allowed_roots = _get_allowed_roots(project_path)
    if allowed_roots and not any(_is_subpath(real_path, root) for root in allowed_roots):
        raise IntegrityError(f"Dependency outside allowed roots: {real_path}")

    # Disallow symlink tricks that escape allowed roots
    if path.is_symlink():
        raise IntegrityError(f"Symlinked dependency not allowed: {path}")

    # verify_item handles all file types via MetadataManager → get_signature_format().
    # ItemType.TOOL is used because all files under .ai/tools/ are tool artifacts,
    # even helper modules without __executor_id__. The signing system only needs
    # the file extension to find the correct comment prefix.
    return verify_item(real_path, ItemType.TOOL, project_path=project_path)
