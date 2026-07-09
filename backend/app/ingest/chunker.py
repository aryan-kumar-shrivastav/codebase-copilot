"""
AST-aware chunking.

The single biggest quality lever for code RAG is chunking by structural
unit (function / class / method) instead of fixed-size token windows —
fixed windows routinely cut a function in half and destroy the very thing
retrieval needs to match against. This module uses tree-sitter to find
top-level symbols per language, and falls back to a paragraph/blank-line
splitter for languages/files it doesn't have a grammar for.

Each Chunk carries the metadata (symbol name/type, line range) that both
vector search and symbol_search rely on downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field

try:
    from tree_sitter_languages import get_parser
    _TREE_SITTER_AVAILABLE = True
except Exception:  # pragma: no cover - environment without tree-sitter builds
    _TREE_SITTER_AVAILABLE = False

EXT_TO_LANG = {
    ".py": "python", ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "tsx", ".go": "go", ".rs": "rust",
    ".java": "java", ".rb": "ruby", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".hpp": "cpp", ".cs": "c_sharp",
}

# node types (per tree-sitter grammar) we treat as "a chunk-worthy symbol"
SYMBOL_NODE_TYPES = {
    "function_definition", "class_definition",                      # python
    "function_declaration", "method_definition", "class_declaration",  # js/ts
    "function_item", "impl_item", "struct_item",                     # rust
    "method_declaration",                                             # java/go/c#
}

MAX_CHUNK_CHARS = 6000  # hard ceiling; oversized symbols get truncated with a flag


@dataclass
class CodeChunk:
    file_path: str
    content: str
    start_line: int
    end_line: int
    symbol_name: str | None = None
    symbol_type: str | None = None
    language: str | None = None
    meta: dict = field(default_factory=dict)


def _lang_for_path(path: str) -> str | None:
    for ext, lang in EXT_TO_LANG.items():
        if path.endswith(ext):
            return lang
    return None


def _node_name(node, source: bytes) -> str | None:
    for child in node.children:
        if child.type in ("identifier", "property_identifier", "type_identifier"):
            return source[child.start_byte:child.end_byte].decode("utf-8", "ignore")
    return None


def _walk_symbols(node, source: bytes, depth: int = 0, parent_name: str | None = None):
    """Yield (node, qualified_name) for each symbol node. Always recurses
    through wrapper nodes (blocks, bodies) to find nested symbols wherever
    they live in the tree, but `depth` only increases when stepping inside
    a symbol node itself — so a class's methods are captured individually,
    while a function's inner closures are not chunked separately."""
    for child in node.children:
        if child.type in SYMBOL_NODE_TYPES:
            name = _node_name(child, source) or "<anonymous>"
            qualified = f"{parent_name}.{name}" if parent_name else name
            yield child, qualified
            if depth < 1:
                yield from _walk_symbols(child, source, depth + 1, qualified)
        else:
            yield from _walk_symbols(child, source, depth, parent_name)


def chunk_with_tree_sitter(file_path: str, source_text: str, lang: str) -> list[CodeChunk]:
    parser = get_parser(lang)
    source_bytes = source_text.encode("utf-8")
    tree = parser.parse(source_bytes)

    chunks: list[CodeChunk] = []
    for node, qualified_name in _walk_symbols(tree.root_node, source_bytes):
        start_line = node.start_point[0] + 1
        end_line = node.end_point[0] + 1
        text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", "ignore")
        if not text.strip():
            continue
        symbol_type = (
            node.type.replace("_definition", "")
            .replace("_declaration", "")
            .replace("_item", "")
        )
        chunks.append(CodeChunk(
            file_path=file_path,
            content=text[:MAX_CHUNK_CHARS],
            start_line=start_line,
            end_line=end_line,
            symbol_name=qualified_name,
            symbol_type=symbol_type,
            language=lang,
            meta={"truncated": len(text) > MAX_CHUNK_CHARS},
        ))

    if not chunks:
        # file had no top-level symbols (e.g. a config/script file) — treat
        # the whole file as one module-level chunk
        chunks.append(CodeChunk(
            file_path=file_path,
            content=source_text[:MAX_CHUNK_CHARS],
            start_line=1,
            end_line=source_text.count("\n") + 1,
            symbol_name=None,
            symbol_type="module",
            language=lang,
        ))
    return chunks


def chunk_generic(file_path: str, source_text: str, lang: str | None) -> list[CodeChunk]:
    """Fallback for languages without a tree-sitter grammar wired up, or
    non-code text files (markdown, config, etc): split on blank-line runs,
    then hard-wrap anything still oversized."""
    lines = source_text.split("\n")
    blocks: list[tuple[int, int, str]] = []
    buf, buf_start = [], 1
    for i, line in enumerate(lines, start=1):
        if line.strip() == "" and buf:
            blocks.append((buf_start, i - 1, "\n".join(buf)))
            buf, buf_start = [], i + 1
        else:
            if not buf:
                buf_start = i
            buf.append(line)
    if buf:
        blocks.append((buf_start, len(lines), "\n".join(buf)))

    chunks = []
    for start, end, text in blocks:
        if not text.strip():
            continue
        for offset in range(0, len(text), MAX_CHUNK_CHARS):
            piece = text[offset:offset + MAX_CHUNK_CHARS]
            chunks.append(CodeChunk(
                file_path=file_path, content=piece, start_line=start, end_line=end,
                symbol_name=None, symbol_type="block", language=lang,
            ))
    return chunks or [CodeChunk(file_path=file_path, content=source_text[:MAX_CHUNK_CHARS],
                                 start_line=1, end_line=len(lines), symbol_type="module", language=lang)]


def chunk_file(file_path: str, source_text: str) -> list[CodeChunk]:
    lang = _lang_for_path(file_path)
    if lang and _TREE_SITTER_AVAILABLE:
        try:
            return chunk_with_tree_sitter(file_path, source_text, lang)
        except Exception:
            pass  # fall through to generic chunking on any parser hiccup
    return chunk_generic(file_path, source_text, lang)
