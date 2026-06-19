"""
Tests for scripts/split_po_file.py
"""

import os
import polib
import pytest

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
)  # 5 simple + 1 plural (6 translated), 1 untranslated = 7 total


class TestSplitPoFile:
    def test_single_chunk_when_entries_fit(self, tmp_path):
        chunks = split_po_file(SIMPLE_PO, str(tmp_path), chunk_size=500)
        assert len(chunks) == 1

    def test_splits_into_correct_number_of_chunks(self, tmp_path):
        # 7 total entries, chunk_size=2 → 4 chunks
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=2)
        assert len(chunks) == 4

    def test_chunk_boundary_is_exact_multiple(self, tmp_path):
        # 6 translated entries with translated_only, chunk_size=3 → exactly 2 chunks
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=3, translated_only=True)
        assert len(chunks) == 2

    def test_total_entries_equals_all_count(self, tmp_path):
        po = polib.pofile(LARGE_PO)
        expected = len(list(po))

        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=2)
        total = sum(len(polib.pofile(c)) for c in chunks)
        assert total == expected

    def test_untranslated_entries_included_by_default(self, tmp_path):
        po = polib.pofile(LARGE_PO)
        assert len(po.untranslated_entries()) > 0, "fixture must have untranslated entries"

        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=500)
        total = sum(len(polib.pofile(c)) for c in chunks)
        assert total == len(list(po))

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

        assert len(plural_chunks) == 1, "plural entry should appear in exactly one chunk"

    def test_chunk_files_are_valid_po(self, tmp_path):
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=2)
        for chunk_path in chunks:
            po = polib.pofile(chunk_path)
            assert len(po) > 0

    def test_returns_chunks_for_all_untranslated_by_default(self, tmp_path):
        untranslated_po = polib.POFile()
        untranslated_po.metadata = {
            "Language": "ar",
            "Content-Type": "text/plain; charset=UTF-8",
        }
        untranslated_po.append(polib.POEntry(msgid="Hello", msgstr=""))
        input_path = str(tmp_path / "untranslated.po")
        untranslated_po.save(input_path)

        chunks = split_po_file(input_path, str(tmp_path / "out"), chunk_size=500)
        assert len(chunks) == 1

    def test_output_dir_created_if_missing(self, tmp_path):
        new_dir = str(tmp_path / "deeply" / "nested")
        chunks = split_po_file(LARGE_PO, new_dir, chunk_size=500)
        assert os.path.isdir(new_dir)
        assert len(chunks) > 0

    def test_chunk_files_named_sequentially(self, tmp_path):
        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=2)
        basenames = [os.path.basename(c) for c in chunks]
        assert basenames == ["chunk_0000.po", "chunk_0001.po", "chunk_0002.po", "chunk_0003.po"]

    def test_raises_on_non_positive_chunk_size(self, tmp_path):
        with pytest.raises(ValueError, match="chunk_size must be a positive integer"):
            split_po_file(LARGE_PO, str(tmp_path), chunk_size=0)

    # translated_only=True (--translated-only) tests

    def test_translated_only_excludes_untranslated(self, tmp_path):
        po = polib.pofile(LARGE_PO)
        assert len(po.untranslated_entries()) > 0, "fixture must have untranslated entries"

        chunks = split_po_file(LARGE_PO, str(tmp_path), chunk_size=500, translated_only=True)
        chunk_po = polib.pofile(chunks[0])
        assert len(chunk_po.untranslated_entries()) == 0

    def test_translated_only_total_less_than_all_entries(self, tmp_path):
        po = polib.pofile(LARGE_PO)
        assert len(po.untranslated_entries()) > 0, "fixture must have untranslated entries"

        chunks_translated = split_po_file(LARGE_PO, str(tmp_path / "translated"), chunk_size=500, translated_only=True)
        chunks_all = split_po_file(LARGE_PO, str(tmp_path / "all"), chunk_size=500)

        total_translated = sum(len(polib.pofile(c)) for c in chunks_translated)
        total_all = sum(len(polib.pofile(c)) for c in chunks_all)
        assert total_all > total_translated

    def test_translated_only_returns_empty_list_when_nothing_translated(self, tmp_path):
        untranslated_po = polib.POFile()
        untranslated_po.metadata = {
            "Language": "ar",
            "Content-Type": "text/plain; charset=UTF-8",
        }
        untranslated_po.append(polib.POEntry(msgid="Hello", msgstr=""))
        input_path = str(tmp_path / "untranslated.po")
        untranslated_po.save(input_path)

        chunks = split_po_file(input_path, str(tmp_path / "out"), chunk_size=500, translated_only=True)
        assert chunks == []
