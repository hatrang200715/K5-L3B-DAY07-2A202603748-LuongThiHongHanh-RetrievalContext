"""Validate Advanced benchmark counts, question/gold separation, and PDF evidence."""
import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from pypdf import PdfReader


MINIMUMS = {
    'test': {
        'table': 6,
        'image_diagram': 5,
        'chart': 5,
        'multi_hop': 4,
        'text': 4,
        'insufficient_evidence': 6,
    },
    'dev': {'insufficient_evidence': 3},
}
VISUAL_EVIDENCE_KINDS = {
    'map_legend', 'map_label', 'map_caption', 'conceptual_diagram', 'chart',
}


def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFC', text)).strip().casefold()


def main():
    parser = argparse.ArgumentParser(description='Validate the advanced PDF benchmark')
    parser.add_argument('--questions', type=Path, default=Path('benchmark/advanced/questions.json'))
    parser.add_argument('--gold', type=Path, default=Path('benchmark/advanced/gold.json'))
    parser.add_argument('--pdf', type=Path, default=Path('data/Final - Designed Viet Nam 2045 Full Report-En.pdf.pdf'))
    args = parser.parse_args()
    question_data = json.loads(args.questions.read_text(encoding='utf-8'))
    gold_data = json.loads(args.gold.read_text(encoding='utf-8'))
    questions = question_data['questions']
    gold = gold_data['entries']
    question_ids = [item['id'] for item in questions]
    gold_ids = [item['question_id'] for item in gold]
    if len(set(question_ids)) != len(question_ids) or len(set(gold_ids)) != len(gold_ids):
        raise ValueError('Duplicate question or gold ID')
    if set(question_ids) != set(gold_ids):
        raise ValueError('Question IDs and gold IDs differ')
    by_id = {item['question_id']: item for item in gold}
    for split, minimums in MINIMUMS.items():
        cases = [item for item in questions if item['split'] == split]
        counts = Counter(item['group'] for item in cases)
        if split == 'test' and len(cases) < 30:
            raise ValueError('Advanced test must contain at least 30 questions')
        answerable = sum(by_id[item['id']]['answerability'] == 'answerable' for item in cases)
        if split == 'test' and answerable < 24:
            raise ValueError('Advanced test must contain at least 24 answerable questions')
        if split == 'dev' and answerable < 15:
            raise ValueError('Advanced dev must contain at least 15 answerable questions')
        for group, minimum in minimums.items():
            if counts[group] < minimum:
                raise ValueError(f'{split} needs {minimum} {group} questions, found {counts[group]}')

    reader = PdfReader(args.pdf)
    if len(reader.pages) != 136:
        raise ValueError(f'Expected the 136-page source PDF, got {len(reader.pages)}')
    extracted = {page: normalize(reader.pages[page - 1].extract_text() or '')
                 for page in range(1, len(reader.pages) + 1)}
    checked_quotes = 0
    missing_quotes = []
    for entry in gold:
        if entry['answerability'] != 'answerable':
            continue
        if not entry.get('evidence'):
            raise ValueError(f'{entry["question_id"]}: answerable item has no evidence')
        for evidence in entry['evidence']:
            quote = evidence.get('quote', '')
            quote_parts = [normalize(part) for part in quote.split(';') if normalize(part)]
            quote_found = all(part in extracted[evidence['page']] for part in quote_parts)
            if quote and evidence.get('kind') not in VISUAL_EVIDENCE_KINDS and not quote_found:
                missing_quotes.append((entry['question_id'], evidence['page'], quote))
            elif quote and evidence.get('kind') not in VISUAL_EVIDENCE_KINDS:
                checked_quotes += 1
            elif not quote and evidence.get('kind') not in VISUAL_EVIDENCE_KINDS:
                raise ValueError(f'{entry["question_id"]}: text/table evidence requires an exact quote')
    if missing_quotes:
        raise ValueError(f'Gold quote not found on cited PDF page: {missing_quotes[:5]}')
    print(json.dumps({
        'questions': len(questions),
        'dev': dict(Counter(item['group'] for item in questions if item['split'] == 'dev')),
        'test': dict(Counter(item['group'] for item in questions if item['split'] == 'test')),
        'gold_entries': len(gold),
        'source_pages': len(reader.pages),
        'gold_quotes_verified_in_source_pdf': checked_quotes,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
