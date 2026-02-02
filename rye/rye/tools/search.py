"""Search tool - find directives, tools, or knowledge entries.

Implements keyword-based search with:
- Boolean operators (AND, OR, NOT)
- Wildcards (*)
- Phrase search (quotes)
- Field-specific search
- Meta-field filters
- Fuzzy matching (Levenshtein distance)
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional

from rye.utils.resolvers import get_user_space
from rye.constants import ItemType
from rye.utils.path_utils import get_system_space

logger = logging.getLogger(__name__)


@dataclass
class SearchOptions:
    """Search configuration options."""

    query: str = ""
    item_type: str = ""
    source: str = "project"
    project_path: str = ""
    limit: int = 10
    offset: int = 0
    sort_by: str = "score"
    fields: Dict[str, str] = field(default_factory=dict)
    filters: Dict[str, Any] = field(default_factory=dict)
    fuzzy: Dict[str, Any] = field(default_factory=dict)


class QueryParser:
    """Parse search queries with boolean operators, phrases, and wildcards."""

    def __init__(self, query: str):
        self.query = query
        self.pos = 0

    def parse(self) -> "QueryNode":
        """Parse query into AST."""
        if not self.query.strip():
            return MatchAllNode()
        return self._parse_or()

    def _parse_or(self) -> "QueryNode":
        """Parse OR expressions."""
        left = self._parse_and()
        while self._match_keyword("OR"):
            right = self._parse_and()
            left = OrNode(left, right)
        return left

    def _parse_and(self) -> "QueryNode":
        """Parse AND expressions (implicit or explicit)."""
        left = self._parse_not()
        while True:
            if self._match_keyword("AND"):
                right = self._parse_not()
                left = AndNode(left, right)
            elif self._peek_not() or self._peek_term():
                right = self._parse_not()
                left = AndNode(left, right)
            else:
                break
        return left

    def _parse_not(self) -> "QueryNode":
        """Parse NOT expressions."""
        if self._match_keyword("NOT"):
            return NotNode(self._parse_primary())
        return self._parse_primary()

    def _peek_not(self) -> bool:
        """Check if NOT keyword is ahead."""
        self._skip_whitespace()
        if self.pos >= len(self.query):
            return False
        remaining = (
            self.query[self.pos :].split()[0].upper()
            if self.query[self.pos :].split()
            else ""
        )
        return remaining == "NOT"

    def _parse_primary(self) -> "QueryNode":
        """Parse primary expressions (terms, phrases, groups)."""
        self._skip_whitespace()

        if self.pos >= len(self.query):
            return MatchAllNode()

        if self.query[self.pos] == "(":
            self.pos += 1
            node = self._parse_or()
            self._skip_whitespace()
            if self.pos < len(self.query) and self.query[self.pos] == ")":
                self.pos += 1
            return node

        if self.query[self.pos] == '"':
            return self._parse_phrase()

        return self._parse_term()

    def _parse_phrase(self) -> "QueryNode":
        """Parse quoted phrase."""
        self.pos += 1  # Skip opening quote
        start = self.pos
        while self.pos < len(self.query) and self.query[self.pos] != '"':
            self.pos += 1
        phrase = self.query[start : self.pos]
        if self.pos < len(self.query):
            self.pos += 1  # Skip closing quote
        return PhraseNode(phrase)

    def _parse_term(self) -> "QueryNode":
        """Parse single term (may include wildcards)."""
        start = self.pos
        while self.pos < len(self.query) and not self.query[self.pos].isspace():
            if self.query[self.pos] in '()"':
                break
            self.pos += 1
        term = self.query[start : self.pos]

        if not term or term.upper() in ("AND", "OR", "NOT"):
            return MatchAllNode()

        if "*" in term:
            return WildcardNode(term)
        return TermNode(term)

    def _match_keyword(self, keyword: str) -> bool:
        """Check if next token matches keyword."""
        self._skip_whitespace()
        if self.query[self.pos :].upper().startswith(keyword):
            after = self.pos + len(keyword)
            if after >= len(self.query) or self.query[after].isspace():
                self.pos = after
                return True
        return False

    def _peek_term(self) -> bool:
        """Check if there's a term ahead (not operator or end)."""
        self._skip_whitespace()
        if self.pos >= len(self.query):
            return False
        if self.query[self.pos] in "()":
            return False
        remaining = (
            self.query[self.pos :].split()[0].upper()
            if self.query[self.pos :].split()
            else ""
        )
        return remaining not in ("AND", "OR", "NOT", "")

    def _skip_whitespace(self):
        """Skip whitespace."""
        while self.pos < len(self.query) and self.query[self.pos].isspace():
            self.pos += 1


class QueryNode:
    """Base class for query AST nodes."""

    def matches(self, text: str, fuzzy_distance: int = 0) -> bool:
        raise NotImplementedError


class MatchAllNode(QueryNode):
    """Matches everything."""

    def matches(self, text: str, fuzzy_distance: int = 0) -> bool:
        del text, fuzzy_distance
        return True


class TermNode(QueryNode):
    """Single term match."""

    def __init__(self, term: str):
        self.term = term.lower()

    def matches(self, text: str, fuzzy_distance: int = 0) -> bool:
        text_lower = text.lower()
        if self.term in text_lower:
            return True
        if fuzzy_distance > 0:
            return self._fuzzy_match(text_lower, fuzzy_distance)
        return False

    def _fuzzy_match(self, text: str, max_distance: int) -> bool:
        """Check if term fuzzy-matches any word in text."""
        words = re.findall(r"\w+", text)
        for word in words:
            if levenshtein_distance(self.term, word) <= max_distance:
                return True
        return False


class PhraseNode(QueryNode):
    """Exact phrase match."""

    def __init__(self, phrase: str):
        self.phrase = phrase.lower()

    def matches(self, text: str, fuzzy_distance: int = 0) -> bool:
        del fuzzy_distance
        return self.phrase in text.lower()


class WildcardNode(QueryNode):
    """Wildcard pattern match."""

    def __init__(self, pattern: str):
        self.pattern = pattern.lower()

    def matches(self, text: str, fuzzy_distance: int = 0) -> bool:
        del fuzzy_distance
        words = re.findall(r"\w+", text.lower())
        for word in words:
            if fnmatch(word, self.pattern):
                return True
        return False


class AndNode(QueryNode):
    """AND boolean operator."""

    def __init__(self, left: QueryNode, right: QueryNode):
        self.left = left
        self.right = right

    def matches(self, text: str, fuzzy_distance: int = 0) -> bool:
        return self.left.matches(text, fuzzy_distance) and self.right.matches(
            text, fuzzy_distance
        )


class OrNode(QueryNode):
    """OR boolean operator."""

    def __init__(self, left: QueryNode, right: QueryNode):
        self.left = left
        self.right = right

    def matches(self, text: str, fuzzy_distance: int = 0) -> bool:
        return self.left.matches(text, fuzzy_distance) or self.right.matches(
            text, fuzzy_distance
        )


class NotNode(QueryNode):
    """NOT boolean operator."""

    def __init__(self, child: QueryNode):
        self.child = child

    def matches(self, text: str, fuzzy_distance: int = 0) -> bool:
        return not self.child.matches(text, fuzzy_distance)


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    prev_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (c1 != c2)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row

    return prev_row[-1]


class FilterMatcher:
    """Match items against meta-field filters."""

    @staticmethod
    def matches(item: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if item matches all filters."""
        for field, filter_value in filters.items():
            if not FilterMatcher._match_filter(item, field, filter_value):
                return False
        return True

    @staticmethod
    def _match_filter(item: Dict[str, Any], field: str, filter_value: Any) -> bool:
        """Match single filter."""
        if field == "date_from":
            return FilterMatcher._match_date_from(item, filter_value)
        if field == "date_to":
            return FilterMatcher._match_date_to(item, filter_value)

        item_value = item.get(field) or item.get("metadata", {}).get(field)
        if item_value is None:
            return False

        if isinstance(filter_value, list):
            return item_value in filter_value

        if isinstance(filter_value, str):
            if filter_value.startswith("!"):
                return str(item_value) != filter_value[1:]
            if filter_value.startswith(">="):
                return FilterMatcher._compare_version(item_value, filter_value[2:]) >= 0
            if filter_value.startswith("<="):
                return FilterMatcher._compare_version(item_value, filter_value[2:]) <= 0
            if filter_value.startswith(">"):
                return FilterMatcher._compare_version(item_value, filter_value[1:]) > 0
            if filter_value.startswith("<"):
                return FilterMatcher._compare_version(item_value, filter_value[1:]) < 0
            return str(item_value).lower() == filter_value.lower()

        return item_value == filter_value

    @staticmethod
    def _match_date_from(item: Dict[str, Any], date_str: str) -> bool:
        """Check if item date >= filter date."""
        item_date = item.get("created_at") or item.get("metadata", {}).get("created_at")
        if not item_date:
            return True
        try:
            filter_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if isinstance(item_date, str):
                item_date = datetime.fromisoformat(item_date.replace("Z", "+00:00"))
            return item_date >= filter_date
        except (ValueError, TypeError):
            return True

    @staticmethod
    def _match_date_to(item: Dict[str, Any], date_str: str) -> bool:
        """Check if item date <= filter date."""
        item_date = item.get("created_at") or item.get("metadata", {}).get("created_at")
        if not item_date:
            return True
        try:
            filter_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if isinstance(item_date, str):
                item_date = datetime.fromisoformat(item_date.replace("Z", "+00:00"))
            return item_date <= filter_date
        except (ValueError, TypeError):
            return True

    @staticmethod
    def _compare_version(v1: str, v2: str) -> int:
        """Compare semantic versions. Returns -1, 0, or 1."""
        try:
            parts1 = [int(x) for x in str(v1).split(".")]
            parts2 = [int(x) for x in str(v2).split(".")]
            while len(parts1) < 3:
                parts1.append(0)
            while len(parts2) < 3:
                parts2.append(0)
            for p1, p2 in zip(parts1, parts2):
                if p1 < p2:
                    return -1
                if p1 > p2:
                    return 1
            return 0
        except (ValueError, AttributeError):
            return 0


class SearchTool:
    """Search for items by query with advanced matching."""

    FIELD_WEIGHTS = {
        "title": 3.0,
        "name": 3.0,
        "description": 2.0,
        "category": 1.5,
        "content": 1.0,
    }

    def __init__(self, user_space: Optional[str] = None):
        """Initialize search tool."""
        self.user_space = user_space or str(get_user_space())

    async def handle(self, **kwargs) -> Dict[str, Any]:
        """Handle search request."""
        opts = SearchOptions(
            query=kwargs["query"],
            item_type=kwargs["item_type"],
            source=kwargs.get("source", "project"),
            project_path=kwargs["project_path"],
            limit=kwargs.get("limit", 10),
            offset=kwargs.get("offset", 0),
            sort_by=kwargs.get("sort_by", "score"),
            fields=kwargs.get("fields") or {},
            filters=kwargs.get("filters") or {},
            fuzzy=kwargs.get("fuzzy") or {},
        )

        logger.debug(
            f"Search: item_type={opts.item_type}, query={opts.query}, source={opts.source}"
        )

        try:
            query_ast = QueryParser(opts.query).parse()
            search_paths = self._resolve_paths(opts.project_path, opts.source)
            results = self._search_items(search_paths, opts, query_ast)
            results = self._sort_results(results, opts.sort_by)
            total = len(results)
            results = results[opts.offset : opts.offset + opts.limit]

            return {
                "status": "success",
                "results": results,
                "total": total,
                "query": opts.query,
                "item_type": opts.item_type,
                "source": opts.source,
                "limit": opts.limit,
                "offset": opts.offset,
                "search_type": "keyword",
            }
        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return {"status": "error", "error": str(e), "query": opts.query}

    def _resolve_paths(self, project_path: str, source: str) -> List[Path]:
        """Resolve search paths based on source."""
        paths = []

        if source in ("project", "all") and project_path:
            project_ai = Path(project_path) / ".ai"
            if project_ai.exists():
                paths.append(project_ai)

        if source in ("user", "all"):
            user_ai = Path(self.user_space)
            if user_ai.exists():
                paths.append(user_ai)

        if source in ("system", "all"):
            system_ai = get_system_space()
            if system_ai.exists():
                paths.append(system_ai)

        return paths

    def _search_items(
        self, search_paths: List[Path], opts: SearchOptions, query_ast: QueryNode
    ) -> List[Dict[str, Any]]:
        """Search for items matching query."""
        results = []
        fuzzy_distance = (
            opts.fuzzy.get("max_distance", 0) if opts.fuzzy.get("enabled") else 0
        )

        for base_path in search_paths:
            type_dir = ItemType.TYPE_DIRS.get(opts.item_type)
            if not type_dir:
                continue

            search_dir = base_path / type_dir
            if not search_dir.exists():
                continue

            for file_path in search_dir.rglob("*"):
                if file_path.is_file() and not file_path.name.startswith("_"):
                    item = self._extract_metadata(file_path, opts.item_type)
                    if not item:
                        continue

                    if not self._matches_query(item, query_ast, opts, fuzzy_distance):
                        continue

                    if opts.filters and not FilterMatcher.matches(item, opts.filters):
                        continue

                    score = self._score_item(item, opts, fuzzy_distance)
                    item["score"] = score
                    item["type"] = opts.item_type
                    results.append(item)

        return results

    def _matches_query(
        self,
        item: Dict[str, Any],
        query_ast: QueryNode,
        opts: SearchOptions,
        fuzzy_distance: int,
    ) -> bool:
        """Check if item matches query AST and field-specific searches."""
        searchable_text = self._get_searchable_text(item)
        if not query_ast.matches(searchable_text, fuzzy_distance):
            return False

        for field_name, field_query in opts.fields.items():
            field_value = str(item.get(field_name, ""))
            if field_name == "content":
                field_value = item.get("preview", "")

            field_ast = QueryParser(field_query).parse()
            if not field_ast.matches(field_value, fuzzy_distance):
                return False

        return True

    def _get_searchable_text(self, item: Dict[str, Any]) -> str:
        """Get all searchable text from item."""
        parts = []
        for field in ["name", "title", "description", "category", "preview"]:
            val = item.get(field, "")
            if val:
                parts.append(str(val))
        return " ".join(parts)

    def _score_item(
        self, item: Dict[str, Any], opts: SearchOptions, fuzzy_distance: int
    ) -> float:
        """Score item against query."""
        if not opts.query and not opts.fields:
            return 1.0

        query_ast = QueryParser(opts.query).parse() if opts.query else MatchAllNode()
        total_score = 0.0
        max_score = sum(self.FIELD_WEIGHTS.values())

        for field_name, weight in self.FIELD_WEIGHTS.items():
            field_value = str(item.get(field_name, ""))
            if field_name == "content":
                field_value = item.get("preview", "")

            if query_ast.matches(field_value, fuzzy_distance):
                total_score += weight

        for field_name, field_query in opts.fields.items():
            field_value = str(item.get(field_name, ""))
            field_ast = QueryParser(field_query).parse()
            weight = self.FIELD_WEIGHTS.get(field_name, 1.0)
            if field_ast.matches(field_value, fuzzy_distance):
                total_score += weight
                max_score += weight

        return min(1.0, total_score / max_score) if max_score > 0 else 0.0

    def _sort_results(
        self, results: List[Dict[str, Any]], sort_by: str
    ) -> List[Dict[str, Any]]:
        """Sort results by specified field."""
        if sort_by == "score":
            return sorted(results, key=lambda x: x.get("score", 0), reverse=True)
        elif sort_by == "date":
            return sorted(
                results,
                key=lambda x: x.get("created_at")
                or x.get("metadata", {}).get("created_at", ""),
                reverse=True,
            )
        elif sort_by == "name":
            return sorted(results, key=lambda x: x.get("name", "").lower())
        return results

    def _extract_metadata(
        self, file_path: Path, item_type: str
    ) -> Optional[Dict[str, Any]]:
        """Extract metadata from file."""
        try:
            content = file_path.read_text(encoding="utf-8")
            name = file_path.stem

            path_str = str(file_path)
            if "site-packages/rye" in path_str:
                source = "system"
            elif str(self.user_space) in path_str:
                source = "user"
            else:
                source = "project"

            metadata: Dict[str, Any] = {
                "id": name,
                "name": name,
                "title": name,
                "description": "",
                "preview": content[:200],
                "source": source,
                "path": str(file_path),
                "score": 0.0,
                "metadata": {},
            }

            if item_type == ItemType.DIRECTIVE:
                metadata.update(self._extract_directive_meta(content))
            elif item_type == ItemType.TOOL:
                metadata.update(self._extract_tool_meta(content))
            elif item_type == ItemType.KNOWLEDGE:
                metadata.update(self._extract_knowledge_meta(content))

            return metadata
        except Exception as e:
            logger.debug(f"Failed to extract metadata from {file_path}: {e}")
            return None

    def _extract_directive_meta(self, content: str) -> Dict[str, Any]:
        """Extract metadata from directive XML."""
        result: Dict[str, Any] = {"title": "", "description": "", "metadata": {}}

        if 'name="' in content:
            match = re.search(r'name="([^"]+)"', content)
            if match:
                result["title"] = match.group(1)
                result["name"] = match.group(1)

        if 'version="' in content:
            match = re.search(r'version="([^"]+)"', content)
            if match:
                result["metadata"]["version"] = match.group(1)

        desc_match = re.search(r"<description>(.*?)</description>", content, re.DOTALL)
        if desc_match:
            result["description"] = desc_match.group(1).strip()

        category_match = re.search(r"<category>(.*?)</category>", content)
        if category_match:
            result["category"] = category_match.group(1).strip()
            result["metadata"]["category"] = category_match.group(1).strip()

        return result

    def _extract_tool_meta(self, content: str) -> Dict[str, Any]:
        """Extract metadata from tool file."""
        result: Dict[str, Any] = {"metadata": {}}

        if "__version__" in content:
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                result["metadata"]["version"] = match.group(1)

        if "__category__" in content:
            match = re.search(r'__category__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                result["category"] = match.group(1)
                result["metadata"]["category"] = match.group(1)

        if "__description__" in content:
            match = re.search(r'__description__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                result["description"] = match.group(1)

        docstring_match = re.search(r'^"""(.*?)"""', content, re.DOTALL | re.MULTILINE)
        if docstring_match and not result.get("description"):
            lines = docstring_match.group(1).strip().split("\n")
            result["description"] = lines[0] if lines else ""

        return result

    def _extract_knowledge_meta(self, content: str) -> Dict[str, Any]:
        """Extract metadata from knowledge frontmatter."""
        result: Dict[str, Any] = {"title": "", "description": "", "metadata": {}}

        if content.startswith("---"):
            lines = content.split("\n")
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip().strip("'\"")

                    if key == "title":
                        result["title"] = value
                    elif key == "description":
                        result["description"] = value
                    elif key == "category":
                        result["category"] = value
                        result["metadata"]["category"] = value
                    elif key == "tags":
                        if value.startswith("[") and value.endswith("]"):
                            tags = [
                                t.strip().strip("'\"") for t in value[1:-1].split(",")
                            ]
                            result["metadata"]["tags"] = tags
                        else:
                            result["metadata"]["tags"] = [value]
                    else:
                        result["metadata"][key] = value

        return result
