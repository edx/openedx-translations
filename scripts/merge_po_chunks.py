"""
Merge translated PO chunk files returned by the ai-translations API into a
single PO file.

Uses the last chunk's header metadata so that PO-Revision-Date reflects when
the translation job completed rather than when it started.
"""

import argparse

import polib


def merge_po_chunks(chunk_paths, output_path):
    """
    Merge a list of PO chunk files into a single PO file at output_path.

    Header metadata is taken from the last chunk, which has the most recent
    PO-Revision-Date since chunks are translated sequentially.

    Returns the merged POFile.
    """
    chunks = [polib.pofile(p) for p in chunk_paths]

    result = polib.POFile()
    result.metadata = chunks[-1].metadata.copy()
    result.metadata_is_fuzzy = chunks[-1].metadata_is_fuzzy

    for chunk in chunks:
        result.extend(chunk)

    result.save(output_path)
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Merge translated PO chunk files into a single PO file.',
    )
    parser.add_argument('--output', required=True, help='Path to write the merged PO file')
    parser.add_argument('chunks', nargs='+', help='Chunk PO files to merge, in order')
    args = parser.parse_args()

    merge_po_chunks(args.chunks, args.output)


if __name__ == '__main__':
    main()
