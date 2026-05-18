"""
Tests for scripts/split_po_file.py
"""

import os
import pytest
import polib

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

SIMPLE_PO = os.path.join(FIXTURE_DIR, "django.po")  # 1 translated entry
LARGE_PO = os.path.join(
    FIXTURE_DIR, "django_large.po"
)  # 5 simple + 1 plural (6 translated), 1 untranslated


class TestSplitPoFile:
    def test_single_chunk_when_entries_fit(self, tmp_path):
        chunks = split_po_file(SIMPLE_PO, str(tmp_path), chunk_size=500)
        assert len(chunks) == 1

    def test_splits_into_correct_number_of_chunks(self, tmp_path):
        # 6 translated entries, chunk_size=2 → 3 chunks
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=2)
        assert len(chunks) == 3

    def test_chunk_boundary_is_exact_multiple(self, tmp_path):
        # 6 translated entries, chunk_size=3 → exactly 2 chunks
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=3)
        assert len(chunks) == 2

    def test_total_entries_equals_translated_count(self, tmp_path):
        po = polib.pofile(LARGE_PO)
        expected = len(po.translated_entries())

        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=2)
        total = sum(len(polib.pofile(c)) for c in chunks)
        assert total == expected

    def test_untranslated_entries_excluded(self, tmp_path):
        po = polib.pofile(LARGE_PO)
        assert (
            len(po.untranslated_entries()) > 0
        ), "fixture must have untranslated entries"

        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=500)
        chunk_po = polib.pofile(chunks[0])
        assert len(chunk_po.untranslated_entries()) == 0

    def test_header_metadata_preserved_in_every_chunk(self, tmp_path):
        original = polib.pofile(LARGE_PO)
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=2)

        for chunk_path in chunks:
            chunk = polib.pofile(chunk_path)
            assert chunk.metadata == original.metadata

    def test_plural_entry_kept_whole_in_one_chunk(self, tmp_path):
        # chunk_size=1 forces each entry into its own chunk; the plural entry
        # must appear entirely within a single chunk, not split across two.
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=1)

        plural_chunks = []
        for chunk_path in chunks:
            chunk = polib.pofile(chunk_path)
            for entry in chunk:
                if entry.msgid_plural:
                    plural_chunks.append(chunk_path)

        assert (
            len(plural_chunks) == 1
        ), "plural entry should appear in exactly one chunk"

    def test_chunk_files_are_valid_po(self, tmp_path):
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=2)
        for chunk_path in chunks:
            # polib.pofile raises on parse errors
            po = polib.pofile(chunk_path)
            assert len(po) > 0

    def test_returns_empty_list_for_all_untranslated(self, tmp_path):
        untranslated_po = polib.POFile()
        untranslated_po.metadata = {
            "Language": "ar",
            "Content-Type": "text/plain; charset=UTF-8",
        }
        entry = polib.POEntry(msgid="Hello", msgstr="")
        untranslated_po.append(entry)
        input_path = str(tmp_path / "untranslated.po")
        untranslated_po.save(input_path)

        chunks = split_po_file(input_path, str(tmp_path / "out"), chunk_size=500)
        assert chunks == []

    def test_output_dir_created_if_missing(self, tmp_path):
        new_dir = str(tmp_path / "deeply" / "nested")
        chunks = split_po_file(LARGE_PO, new_dir, chunk_size=500)
        assert os.path.isdir(new_dir)
        assert len(chunks) > 0

    def test_chunk_files_named_sequentially(self, tmp_path):
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=2)
        basenames = [os.path.basename(c) for c in chunks]
        assert basenames == ["chunk_0000.po", "chunk_0001.po", "chunk_0002.po"]
