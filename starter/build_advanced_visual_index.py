"""Render every substantive Day 7 PDF page for visual evidence retrieval."""
import argparse
import hashlib
import json
from pathlib import Path

import pymupdf
import yaml


def main():
    parser = argparse.ArgumentParser(description='Render substantive PDF pages as indexed visual evidence')
    parser.add_argument('--pdf', type=Path, default=Path('data/Final - Designed Viet Nam 2045 Full Report-En.pdf.pdf'))
    parser.add_argument('--manifest', type=Path, default=Path('data/day7/manifest.yaml'))
    parser.add_argument('--output', type=Path, default=Path('results/day7/advanced_visual_index'))
    parser.add_argument('--scale', type=float, default=1.2)
    args = parser.parse_args()
    if args.scale <= 0:
        parser.error('--scale must be positive')
    manifest = yaml.safe_load(args.manifest.read_text(encoding='utf-8'))
    source = manifest['source']
    if not args.pdf.is_file():
        raise FileNotFoundError(args.pdf)
    pdf_hash = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    if pdf_hash != source['snapshot_sha256']:
        raise ValueError(f'PDF SHA-256 mismatch: expected {source["snapshot_sha256"]}, got {pdf_hash}')
    pages = []
    for start, end in source['counted_content_page_ranges']:
        pages.extend(range(start, end + 1))
    args.output.mkdir(parents=True, exist_ok=True)
    image_dir = args.output / 'pages'
    image_dir.mkdir(exist_ok=True)
    document = pymupdf.open(args.pdf)
    if len(document) != source['physical_page_count']:
        raise ValueError(f'Expected {source["physical_page_count"]} pages, got {len(document)}')
    rows = []
    for number in pages:
        page = document[number - 1]
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(args.scale, args.scale), alpha=False)
        name = f'page-{number:03}.png'
        path = image_dir / name
        pixmap.save(path)
        rows.append({
            'source_id': source['source_id'],
            'page': number,
            'page_basis': '1-based physical PDF page',
            'page_width_points': page.rect.width,
            'page_height_points': page.rect.height,
            'image_path': str(Path('pages') / name),
            'image_width_pixels': pixmap.width,
            'image_height_pixels': pixmap.height,
            'image_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'source_pdf_sha256': pdf_hash,
            'visual_evidence_region': 'Full page; use page coordinates for a specific figure/table/map.',
        })
    index = {
        'source_id': source['source_id'],
        'source_url': source['source_path_or_url'],
        'source_pdf_sha256': pdf_hash,
        'page_numbering': '1-based physical PDF page',
        'render_scale': args.scale,
        'page_count': len(rows),
        'text_extraction': 'pypdf text remains indexed in day7_A/B/C; this index provides page-image evidence.',
        'pages': rows,
    }
    (args.output / 'index.json').write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(json.dumps({
        'output': str(args.output),
        'page_count': len(rows),
        'source_pdf_sha256': pdf_hash,
        'image_count': len(rows),
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
