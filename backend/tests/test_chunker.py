"""
Unit tests for the AST chunker — the piece with the most retrieval-quality
leverage, so it's the piece worth testing in isolation. Run with:
    pytest backend/tests/test_chunker.py -v
"""
from app.ingest.chunker import chunk_file

PY_SAMPLE = '''import os

class UserService:
    """Handles user auth."""

    def __init__(self, db):
        self.db = db

    def authenticate(self, username, password):
        user = self.db.find_user(username)
        if user and user.check_password(password):
            return user
        return None

def helper_function(x):
    return x * 2
'''


def test_python_class_and_methods_chunked_separately():
    chunks = chunk_file("userservice.py", PY_SAMPLE)
    names = {c.symbol_name for c in chunks}
    assert "UserService" in names
    assert "UserService.__init__" in names
    assert "UserService.authenticate" in names
    assert "helper_function" in names


def test_chunk_line_ranges_are_sane():
    chunks = chunk_file("userservice.py", PY_SAMPLE)
    for c in chunks:
        assert c.start_line >= 1
        assert c.end_line >= c.start_line


def test_module_level_symbol_types():
    chunks = chunk_file("userservice.py", PY_SAMPLE)
    by_name = {c.symbol_name: c for c in chunks}
    assert by_name["UserService"].symbol_type == "class"
    assert by_name["helper_function"].symbol_type == "function"


def test_empty_file_does_not_crash():
    chunks = chunk_file("empty.py", "")
    assert isinstance(chunks, list)


def test_unrecognized_extension_falls_back_to_generic_chunking():
    text = "line one\nline two\n\nblock two line one\nblock two line two\n"
    chunks = chunk_file("notes.txt", text)
    assert len(chunks) >= 1
    assert all(c.symbol_type in ("block", "module") for c in chunks)


def test_file_with_no_top_level_symbols_becomes_one_module_chunk():
    text = "DEBUG = True\nPORT = 8080\n"
    chunks = chunk_file("settings.py", text)
    assert len(chunks) == 1
    assert chunks[0].symbol_type == "module"
