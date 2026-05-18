"""
Split a PO file into smaller chunks for upload to the ai-translations API.

Each chunk is a valid PO file containing the original header metadata and a
subset of entries. Splitting by entry boundaries ensures plural variants
(msgid_plural / msgstr[N]) are never divided across chunks.
"""

import argparse
import os

import polib


def split_po_file(input_path, output_dir, chunk_size=500, translated_only=False):
    """
    Split a PO file into chunks of at most chunk_size entries.

    When translated_only=False (default), all entries are included — correct
    for translation, where source strings with empty msgstrs are the whole point.
    When translated_only=True, only translated entries are included — correct
    for seeding, where untranslated strings have nothing to contribute.

    Returns a list of paths to the written chunk files, in order.
    Returns an empty list if the file contains no qualifying entries.
    """
    po = polib.pofile(input_path)
    entries = po.translated_entries() if translated_only else list(po)

    if not entries:
        return []

    os.makedirs(output_dir, exist_ok=True)

    chunk_paths = []
    for chunk_idx, start in enumerate(range(0, len(entries), chunk_size)):
        chunk = polib.POFile()
        chunk.metadata = po.metadata.copy()
        chunk.metadata_is_fuzzy = po.metadata_is_fuzzy
        chunk.extend(entries[start:start + chunk_size])

        chunk_path = os.path.join(output_dir, f'chunk_{chunk_idx:04d}.po')
        chunk.save(chunk_path)
        chunk_paths.append(chunk_path)

    return chunk_paths


def main():
    parser = argparse.ArgumentParser(
        description='Split a PO file into chunks suitable for the ai-translations API.',
    )
    parser.add_argument('--input', required=True, help='Path to the input PO file')
    parser.add_argument('--output-dir', required=True, help='Directory to write chunk files into')
    parser.add_argument('--chunk-size', type=int, default=500, help='Max entries per chunk (default: 500)')
    parser.add_argument('--translated-only', action='store_true', help='Include only translated entries (for seeding; default includes all entries)')
    args = parser.parse_args()

    chunk_paths = split_po_file(args.input, args.output_dir, args.chunk_size, translated_only=args.translated_only)
    for path in chunk_paths:
        print(path)


if __name__ == '__main__':
    main()
