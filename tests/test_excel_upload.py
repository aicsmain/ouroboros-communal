"""Tests for Excel/CSV upload feature: excel.py tool."""
import pathlib
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(tmp_path: pathlib.Path) -> MagicMock:
    """Create a minimal ToolContext mock pointing at tmp_path."""
    ctx = MagicMock()
    ctx.drive_root = tmp_path
    return ctx


def _setup_uploads(tmp_path: pathlib.Path) -> pathlib.Path:
    uploads = tmp_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return uploads


# ---------------------------------------------------------------------------
# _read_uploaded_file — CSV
# ---------------------------------------------------------------------------

def test_read_csv(tmp_path):
    """_read_uploaded_file parses CSV to markdown table."""
    uploads = _setup_uploads(tmp_path)
    (uploads / "data.csv").write_text("name,value\nAlpha,1\nBeta,2\n")

    from ouroboros.tools.excel import _read_uploaded_file
    ctx = _make_ctx(tmp_path)
    result = _read_uploaded_file(ctx, filename="data.csv")

    assert "name" in result
    assert "Alpha" in result
    assert "Beta" in result
    assert "|" in result  # markdown table format


def test_read_csv_row_limit(tmp_path):
    """_read_uploaded_file truncates at MAX_ROWS (500)."""
    uploads = _setup_uploads(tmp_path)
    rows = ["a,b"] + [f"{i},{i * 2}" for i in range(600)]
    (uploads / "big.csv").write_text("\n".join(rows) + "\n")

    from ouroboros.tools.excel import _read_uploaded_file
    ctx = _make_ctx(tmp_path)
    result = _read_uploaded_file(ctx, filename="big.csv")

    assert "truncated" in result.lower() or "500" in result


def test_read_nonexistent_file(tmp_path):
    """_read_uploaded_file returns error for missing file."""
    _setup_uploads(tmp_path)

    from ouroboros.tools.excel import _read_uploaded_file
    ctx = _make_ctx(tmp_path)
    result = _read_uploaded_file(ctx, filename="missing.csv")

    assert "not found" in result.lower() or "error" in result.lower()


def test_path_traversal_blocked(tmp_path):
    """_read_uploaded_file blocks path traversal attempts."""
    _setup_uploads(tmp_path)

    from ouroboros.tools.excel import _read_uploaded_file
    ctx = _make_ctx(tmp_path)
    result = _read_uploaded_file(ctx, filename="../etc/passwd")

    assert (
        "error" in result.lower()
        or "invalid" in result.lower()
        or "not found" in result.lower()
    )


def test_unsupported_file_type(tmp_path):
    """_read_uploaded_file reads non-Excel/CSV files as plain text fallback."""
    uploads = _setup_uploads(tmp_path)
    (uploads / "notes.txt").write_text("hello world")

    from ouroboros.tools.excel import _read_uploaded_file
    ctx = _make_ctx(tmp_path)
    result = _read_uploaded_file(ctx, filename="notes.txt")

    # Non-structured files are returned as plain text (not an error)
    assert "hello world" in result or "notes.txt" in result


# ---------------------------------------------------------------------------
# _list_uploaded_files
# ---------------------------------------------------------------------------

def test_list_uploaded_files_empty(tmp_path):
    """_list_uploaded_files returns appropriate message when no files."""
    _setup_uploads(tmp_path)

    from ouroboros.tools.excel import _list_uploaded_files
    ctx = _make_ctx(tmp_path)
    result = _list_uploaded_files(ctx)

    assert "no" in result.lower() or "empty" in result.lower()


def test_list_uploaded_files_shows_files(tmp_path):
    """_list_uploaded_files lists file names."""
    uploads = _setup_uploads(tmp_path)
    (uploads / "report.csv").write_text("a,b\n1,2\n")
    (uploads / "data.xlsx").write_bytes(b"fake")

    from ouroboros.tools.excel import _list_uploaded_files
    ctx = _make_ctx(tmp_path)
    result = _list_uploaded_files(ctx)

    assert "report.csv" in result
    assert "data.xlsx" in result


# ---------------------------------------------------------------------------
# get_tools() registration
# ---------------------------------------------------------------------------

def test_get_tools_exported():
    """excel.py exports get_tools() returning ToolEntry objects for both tools."""
    from ouroboros.tools.excel import get_tools
    tools = get_tools()
    assert isinstance(tools, list)
    assert len(tools) >= 2
    # ToolEntry.schema is the raw dict with "name" at top level
    names = [t.schema["name"] for t in tools]
    assert "read_uploaded_file" in names
    assert "list_uploaded_files" in names
