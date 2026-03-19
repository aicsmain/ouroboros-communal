"""Excel/CSV file upload processing tool.

Provides `read_uploaded_file` — parses uploaded Excel (.xlsx, .xls) and CSV files
into structured text that the LLM can reason about.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import pathlib
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry

log = logging.getLogger(__name__)

# Maximum rows/cols to return (prevents context explosion)
MAX_ROWS = 500
MAX_COLS = 50
MAX_CELL_LEN = 200


def _truncate_cell(value: Any) -> str:
    """Convert cell value to string and truncate if too long."""
    if value is None:
        return ""
    s = str(value).strip()
    if len(s) > MAX_CELL_LEN:
        return s[:MAX_CELL_LEN] + "..."
    return s


def _parse_excel(file_path: pathlib.Path, sheet: str | None = None) -> str:
    """Parse an Excel file into markdown table(s)."""
    try:
        import openpyxl
    except ImportError:
        return "\u26a0\ufe0f openpyxl is not installed. Run: pip install openpyxl"

    try:
        wb = openpyxl.load_workbook(str(file_path), read_only=True, data_only=True)
    except Exception as e:
        return f"\u26a0\ufe0f Failed to open Excel file: {e}"

    sheets_to_process = []
    if sheet:
        if sheet in wb.sheetnames:
            sheets_to_process = [sheet]
        else:
            wb.close()
            return f"\u26a0\ufe0f Sheet '{sheet}' not found. Available: {', '.join(wb.sheetnames)}"
    else:
        sheets_to_process = wb.sheetnames

    results = []
    results.append(f"**File:** `{file_path.name}`")
    results.append(f"**Sheets:** {', '.join(wb.sheetnames)}")
    results.append("")

    for sheet_name in sheets_to_process:
        ws = wb[sheet_name]
        rows_data = []
        row_count = 0
        for row in ws.iter_rows(values_only=True):
            if row_count >= MAX_ROWS:
                break
            # Trim trailing None columns
            cells = [_truncate_cell(c) for c in row[:MAX_COLS]]
            # Skip completely empty rows
            if any(c for c in cells):
                rows_data.append(cells)
                row_count += 1

        if not rows_data:
            results.append(f"### Sheet: {sheet_name}\n(empty)\n")
            continue

        # Normalize column count
        max_cols = max(len(r) for r in rows_data)
        for r in rows_data:
            while len(r) < max_cols:
                r.append("")

        results.append(f"### Sheet: {sheet_name}")
        results.append(f"Rows: {len(rows_data)} (of ~{ws.max_row or '?'} total)  |  Columns: {max_cols}")
        results.append("")

        # Markdown table
        header = rows_data[0]
        results.append("| " + " | ".join(h or f"Col{i+1}" for i, h in enumerate(header)) + " |")
        results.append("| " + " | ".join("---" for _ in header) + " |")
        for row in rows_data[1:]:
            results.append("| " + " | ".join(row) + " |")
        results.append("")

        if ws.max_row and ws.max_row > MAX_ROWS:
            results.append(f"*(truncated at {MAX_ROWS} rows, file has ~{ws.max_row})*\n")

    wb.close()
    return "\n".join(results)


def _parse_csv(file_path: pathlib.Path) -> str:
    """Parse a CSV file into a markdown table."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"\u26a0\ufe0f Failed to read CSV: {e}"

    try:
        dialect = csv.Sniffer().sniff(text[:4096])
    except csv.Error:
        dialect = csv.excel

    reader = csv.reader(io.StringIO(text), dialect)
    rows_data = []
    for row in reader:
        if len(rows_data) >= MAX_ROWS:
            break
        cells = [_truncate_cell(c) for c in row[:MAX_COLS]]
        if any(c for c in cells):
            rows_data.append(cells)

    if not rows_data:
        return f"**File:** `{file_path.name}`\n(empty)"

    max_cols = max(len(r) for r in rows_data)
    for r in rows_data:
        while len(r) < max_cols:
            r.append("")

    total_lines = text.count("\n")
    results = [
        f"**File:** `{file_path.name}`",
        f"Rows: {len(rows_data)} (of ~{total_lines} total)  |  Columns: {max_cols}",
        "",
    ]

    header = rows_data[0]
    results.append("| " + " | ".join(h or f"Col{i+1}" for i, h in enumerate(header)) + " |")
    results.append("| " + " | ".join("---" for _ in header) + " |")
    for row in rows_data[1:]:
        results.append("| " + " | ".join(row) + " |")

    if total_lines > MAX_ROWS:
        results.append(f"\n*(truncated at {MAX_ROWS} rows, file has ~{total_lines})*")

    return "\n".join(results)


def _read_uploaded_file(ctx: ToolContext, filename: str, sheet: str | None = None) -> str:
    """Read and parse an uploaded Excel or CSV file."""
    uploads_dir = ctx.drive_root / "uploads"
    file_path = (uploads_dir / filename).resolve()

    # Safety: ensure path is within uploads dir
    if not file_path.is_relative_to(uploads_dir.resolve()):
        return "\u26a0\ufe0f Invalid filename (path traversal detected)"

    if not file_path.exists():
        # List available files
        available = []
        if uploads_dir.exists():
            available = [f.name for f in uploads_dir.iterdir() if f.is_file()]
        if available:
            return f"\u26a0\ufe0f File '{filename}' not found. Available uploads: {', '.join(available)}"
        return f"\u26a0\ufe0f File '{filename}' not found and no files in uploads directory."

    suffix = file_path.suffix.lower()
    if suffix in (".xlsx", ".xls", ".xlsm"):
        return _parse_excel(file_path, sheet=sheet)
    elif suffix == ".csv":
        return _parse_csv(file_path)
    else:
        # Try to read as plain text
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            if len(content) > 50_000:
                content = content[:50_000] + "\n...(truncated)"
            return f"**File:** `{file_path.name}` ({len(content)} chars)\n\n{content}"
        except Exception as e:
            return f"\u26a0\ufe0f Cannot read file: {e}"


def _list_uploaded_files(ctx: ToolContext) -> str:
    """List all files in the uploads directory."""
    uploads_dir = ctx.drive_root / "uploads"
    if not uploads_dir.exists():
        return "No uploaded files yet."

    files = []
    for f in sorted(uploads_dir.iterdir()):
        if f.is_file():
            size = f.stat().st_size
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f} KB"
            else:
                size_str = f"{size / 1024 / 1024:.1f} MB"
            files.append(f"- `{f.name}` ({size_str})")

    if not files:
        return "No uploaded files yet."
    return f"**Uploaded files ({len(files)}):**\n" + "\n".join(files)


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry("read_uploaded_file", {
            "name": "read_uploaded_file",
            "description": (
                "Read and parse an uploaded Excel (.xlsx/.xls) or CSV file into structured text. "
                "Returns markdown tables with headers, data, and sheet info. "
                "Use `sheet` parameter to read a specific sheet from multi-sheet Excel files. "
                "Files are uploaded by the user via the chat interface."
            ),
            "parameters": {"type": "object", "properties": {
                "filename": {"type": "string", "description": "Name of the uploaded file"},
                "sheet": {"type": "string", "description": "Sheet name (Excel only, default: all sheets)"},
            }, "required": ["filename"]},
        }, _read_uploaded_file),
        ToolEntry("list_uploaded_files", {
            "name": "list_uploaded_files",
            "description": "List all files uploaded by the user via the chat interface.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        }, _list_uploaded_files),
    ]
