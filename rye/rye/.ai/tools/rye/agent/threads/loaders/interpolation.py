__version__ = "1.0.0"

import re
from typing import Any, Dict

from .condition_evaluator import resolve_path

_INTERPOLATION_RE = re.compile(r"\$\{([^}]+)\}")


def interpolate(template: Any, context: Dict) -> Any:
    """Interpolate ${...} expressions in a value.

    Works on strings, dicts (recursive), and lists (recursive).
    Non-string leaves are returned as-is.
    """
    if isinstance(template, str):

        def _replace(match):
            path = match.group(1)
            value = resolve_path(context, path)
            return str(value) if value is not None else ""

        return _INTERPOLATION_RE.sub(_replace, template)
    if isinstance(template, dict):
        return {k: interpolate(v, context) for k, v in template.items()}
    if isinstance(template, list):
        return [interpolate(item, context) for item in template]
    return template


def interpolate_action(action: Dict, context: Dict) -> Dict:
    """Interpolate all ${...} in an action's params.

    Preserves primary/item_type/item_id.
    """
    result = dict(action)
    if "params" in result:
        result["params"] = interpolate(result["params"], context)
    return result
