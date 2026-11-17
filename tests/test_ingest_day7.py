import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'starter'))
from ingest_day7 import build_chunk_rows, fixed_chunks, page_section, paragraph_chunks

PAGES = {
    9: 'alpha ' * 300,
    68: 'first paragraph.\n\nsecond paragraph.',
    135: 'short',
}

class IngestDay7Tests(unittest.TestCase):
    def test_fixed_chunks_overlap_and_size(self):
        text = 'x' * 1500
        chunks = fixed_chunks(text)
        self.assertEqual([len(c) for c in chunks], [700, 700, 300])
        self.assertEqual(chunks[0][600:], chunks[1][:100])

    def test_paragraph_chunks_merge_and_split(self):
        merged = paragraph_chunks('short one.\n\nshort two.')
        self.assertEqual(merged, ['short one.\n\nshort two.'])
        long_text = 'y' * 1500
        chunks = paragraph_chunks(long_text)
        self.assertEqual([len(c) for c in chunks], [700, 700, 100])

    def test_page_section_mapping_matches_indexed_metadata(self):
        self.assertEqual(page_section(9), 'introduction')
        self.assertEqual(page_section(16), 'case_for_investment')
        self.assertEqual(page_section(17), 'education')
        self.assertEqual(page_section(49), 'health_nutrition')
        self.assertEqual(page_section(68), 'wash')
        self.assertEqual(page_section(78), 'social_protection')
        self.assertEqual(page_section(89), 'child_protection')
        self.assertEqual(page_section(100), 'cross_cutting')
        self.assertEqual(page_section(113), 'conclusion')
        self.assertEqual(page_section(134), 'annex')
        self.assertIsNone(page_section(8))
        self.assertIsNone(page_section(120))

    def test_chunk_rows_id_format_and_metadata(self):
        rows = build_chunk_rows(PAGES, 'unicef-vietnam-2045-children', 'https://example.org/report.pdf', 'A')
        self.assertEqual(rows[0]['chunk_id'], 'unicef-vietnam-2045-children-p9-fixed-0000')
        self.assertEqual(rows[0]['metadata'], {'section': 'introduction', 'pdf_page': 9})
        self.assertEqual(rows[0]['strategy'], 'day7_A')
        wash = build_chunk_rows(PAGES, 'src', 'https://example.org/report.pdf', 'C')
        self.assertEqual(wash[0]['chunk_id'], 'src-p9-paragraph-0000')
        self.assertEqual(wash[0]['metadata']['section'], 'introduction')
        last = build_chunk_rows({135: 'short'}, 'src', 'u', 'B')
        self.assertEqual(last[0]['chunk_id'], 'src-p135-paragraph-0000')
        self.assertEqual(last[0]['metadata']['section'], 'annex')

if __name__ == '__main__':
    unittest.main()
