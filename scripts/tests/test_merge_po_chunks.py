"""
Tests for scripts/merge_po_chunks.py
"""

import os
import polib
import pytest

from ..merge_po_chunks import merge_po_chunks
from ..split_po_file import split_po_file

SCRIPT_DIR = os.path.dirname(__file__)
FIXTURE_DIR = os.path.join(
    SCRIPT_DIR,
    "mock_translations_dir",
    "demo-xblock",
    "conf",
    "locale",
    "ar",
    "LC_MESSAGES",
)

LARGE_PO = os.path.join(FIXTURE_DIR, "django_large.po")


def make_chunk(tmp_path, name, msgids, metadata):
    """Write a minimal PO file with the given entries and metadata."""
    po = polib.POFile()
    po.metadata = metadata
    for msgid, msgstr in msgids:
        po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
    path = str(tmp_path / name)
    po.save(path)
    return path


class TestMergePoChunks:
    def test_all_entries_present_in_merged_output(self, tmp_path):
        chunks = split_po_file(LARGE_PO, str(tmp_path / "chunks"), chunk_size=2)
        output = str(tmp_path / "merged.po")

        merge_po_chunks(chunks, output)

        original = polib.pofile(LARGE_PO)
        merged = polib.pofile(output)
        assert len(merged) == len(list(original))

    def test_entry_order_preserved(self, tmp_path):
        chunks = split_po_file(LARGE_PO, str(tmp_path / "chunks"), chunk_size=2)
        output = str(tmp_path / "merged.po")

        merge_po_chunks(chunks, output)

        original_msgids = [e.msgid for e in polib.pofile(LARGE_PO)]
        merged_msgids = [e.msgid for e in polib.pofile(output)]
        assert merged_msgids == original_msgids

    def test_header_comes_from_last_chunk(self, tmp_path):
        chunk_a = make_chunk(
            tmp_path, "chunk_a.po",
            [("Hello", "مرحبا")],
            {"Language": "ar", "PO-Revision-Date": "2025-01-01 00:00+0000"},
        )
        chunk_b = make_chunk(
            tmp_path, "chunk_b.po",
            [("Goodbye", "وداعا")],
            {"Language": "ar", "PO-Revision-Date": "2025-06-01 00:00+0000"},
        )
        output = str(tmp_path / "merged.po")

        merge_po_chunks([chunk_a, chunk_b], output)

        merged = polib.pofile(output)
        assert merged.metadata["PO-Revision-Date"] == "2025-06-01 00:00+0000"

    def test_single_chunk_produces_valid_output(self, tmp_path):
        chunks = split_po_file(LARGE_PO, str(tmp_path / "chunks"), chunk_size=500)
        assert len(chunks) == 1
        output = str(tmp_path / "merged.po")

        merge_po_chunks(chunks, output)

        merged = polib.pofile(output)
        assert len(merged) > 0

    def test_output_is_valid_po_file(self, tmp_path):
        chunks = split_po_file(LARGE_PO, str(tmp_path / "chunks"), chunk_size=2)
        output = str(tmp_path / "merged.po")

        merge_po_chunks(chunks, output)

        # polib.pofile raises on parse errors
        polib.pofile(output)

    def test_raises_on_empty_chunk_list(self, tmp_path):
        with pytest.raises(ValueError, match="chunk_paths must not be empty"):
            merge_po_chunks([], str(tmp_path / "merged.po"))

    def test_returns_merged_pofile(self, tmp_path):
        chunks = split_po_file(LARGE_PO, str(tmp_path / "chunks"), chunk_size=2)
        output = str(tmp_path / "merged.po")

        result = merge_po_chunks(chunks, output)

        assert isinstance(result, polib.POFile)
        assert len(result) > 0
