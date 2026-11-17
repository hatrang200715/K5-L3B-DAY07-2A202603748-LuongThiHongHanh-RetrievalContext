"""Ingest the advanced PDF into pgvector using any OpenAI-compatible embedding API."""
import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml
from dotenv import load_dotenv
from pypdf import PdfReader

DEFAULT_BASE_URL = 'https://openrouter.ai/api/v1'
DEFAULT_EMBEDDING_MODEL = 'text-embedding-3-small'
FIXED_SIZE = 700
FIXED_OVERLAP = 100
PARAGRAPH_MAX_SIZE = 700
STRATEGIES = ('A', 'B', 'C')
INDEX_PREFIX = 'day7_'
SECTION_RANGES = (
    (9, 15, 'introduction'),
    (16, 16, 'case_for_investment'),
    (17, 48, 'education'),
    (49, 67, 'health_nutrition'),
    (68, 77, 'wash'),
    (78, 88, 'social_protection'),
    (89, 99, 'child_protection'),
    (100, 112, 'cross_cutting'),
    (113, 114, 'conclusion'),
    (134, 135, 'annex'),
)


def page_section(page):
    for start, end, section in SECTION_RANGES:
        if start <= page <= end:
            return section
    return None


def normalize_page_text(text):
    text = text.replace('\t', ' ')
    return '\n'.join(line.strip() for line in text.split('\n')).strip()


def extract_pages(reader, ranges):
    pages = {}
    for start, end in ranges:
        for number in range(start, end + 1):
            pages[number] = normalize_page_text(reader.pages[number - 1].extract_text() or '')
    return pages


def fixed_chunks(text, size=FIXED_SIZE, overlap=FIXED_OVERLAP):
    if not text:
        return []
    step = size - overlap
    return [text[start:start + size] for start in range(0, len(text), step)]


def paragraph_chunks(text, max_size=PARAGRAPH_MAX_SIZE):
    if not text:
        return []
    units = []
    for paragraph in re.split(r'\n\s*\n', text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for start in range(0, len(paragraph), max_size):
            units.append(paragraph[start:start + max_size])
    chunks = []
    current = ''
    for unit in units:
        candidate = f'{current}\n\n{unit}' if current else unit
        if len(candidate) <= max_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = unit
    if current:
        chunks.append(current)
    return chunks


def build_chunk_rows(pages, source_id, source_url, strategy):
    kind = 'fixed' if strategy == 'A' else 'paragraph'
    chunker = fixed_chunks if strategy == 'A' else paragraph_chunks
    rows = []
    for page in sorted(pages):
        for index, text in enumerate(chunker(pages[page])):
            rows.append({
                'chunk_id': f'{source_id}-p{page}-{kind}-{index:04d}',
                'document_id': source_id,
                'source': source_url,
                'page': page,
                'content': text,
                'metadata': {'section': page_section(page), 'pdf_page': page},
                'strategy': f'{INDEX_PREFIX}{strategy}',
            })
    return rows


def embedding_model_name(config, base_url):
    model = config.get('EMBEDDING_MODEL', DEFAULT_EMBEDDING_MODEL).strip()
    model = model.removeprefix('openrouter:')
    if base_url == DEFAULT_BASE_URL and '/' not in model:
        model = f'openai/{model}'
    return model


class EmbeddingClient:
    def __init__(self, base_url, api_key, model, batch_size=64):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.model = model
        self.batch_size = batch_size
        self.usage = {'requests': 0, 'texts': 0, 'seconds': 0.0}
        self.cache = {}

    def _request(self, texts):
        request = Request(
            f'{self.base_url}/embeddings',
            data=json.dumps({'model': self.model, 'input': texts}).encode('utf-8'),
            headers={'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urlopen(request, timeout=120) as response:
                payload = json.loads(response.read())
        except HTTPError as exc:
            raise RuntimeError(f'Embedding API HTTP {exc.code}: {exc.read().decode("utf-8", errors="replace")[:500]}') from exc
        except URLError as exc:
            raise RuntimeError(f'Embedding API connection error: {exc.reason}') from exc
        data = payload.get('data') or []
        if len(data) != len(texts):
            raise ValueError(f'Embedding API returned {len(data)} vectors for {len(texts)} inputs')
        vectors = [item.get('embedding') for item in data]
        if any(not isinstance(vector, list) or not vector for vector in vectors):
            raise ValueError('Embedding API returned an invalid vector')
        return vectors

    def embed_all(self, texts):
        unique = list(dict.fromkeys(texts))
        pending = [text for text in unique if text not in self.cache]
        for start in range(0, len(pending), self.batch_size):
            batch = pending[start:start + self.batch_size]
            began = time.perf_counter()
            vectors = self._request(batch)
            self.usage['requests'] += 1
            self.usage['seconds'] += time.perf_counter() - began
            for text, vector in zip(batch, vectors):
                self.cache[text] = vector
        self.usage['texts'] += len(unique)
        dimensions = {len(vector) for vector in self.cache.values()}
        if len(dimensions) != 1:
            raise ValueError(f'Inconsistent embedding dimensions: {sorted(dimensions)}')
        return [self.cache[text] for text in texts]


def store_chunks(connection, rows, vectors):
    from psycopg.types.json import Jsonb

    dimensions = len(vectors[0])
    with connection.cursor() as cursor:
        try:
            cursor.execute('CREATE EXTENSION IF NOT EXISTS vector')
            connection.commit()
        except psycopg.Error:
            connection.rollback()
        cursor.execute(f'CREATE TABLE IF NOT EXISTS day6_chunks (chunk_id text PRIMARY KEY, document_id text, source text, page int, content text, metadata jsonb, strategy text, embedding vector({dimensions}))')
        connection.commit()
        strategies = [f'{INDEX_PREFIX}{strategy}' for strategy in STRATEGIES]
        cursor.execute('DELETE FROM day6_chunks WHERE strategy = ANY(%s)', (strategies,))
        for row, vector in zip(rows, vectors):
            cursor.execute(
                'INSERT INTO day6_chunks (chunk_id, document_id, source, page, content, metadata, strategy, embedding) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)',
                (row['chunk_id'], row['document_id'], row['source'], row['page'], row['content'],
                 Jsonb(row['metadata']), row['strategy'], '[' + ','.join(format(value, '.9g') for value in vector) + ']'),
            )
        for strategy in STRATEGIES:
            cursor.execute('SELECT count(*) FROM day6_chunks WHERE strategy = %s', (f'{INDEX_PREFIX}{strategy}',))
            stored = cursor.fetchone()[0]
            expected = sum(1 for row in rows if row['strategy'] == f'{INDEX_PREFIX}{strategy}')
            if stored != expected:
                raise ValueError(f'day7_{strategy}: stored {stored} rows, expected {expected}')
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS day6_chunks_hnsw ON day6_chunks USING hnsw (embedding vector_cosine_ops)')
        except psycopg.Error:
            connection.rollback()
        connection.commit()


def main():
    parser = argparse.ArgumentParser(description='Chunk, embed and index the advanced PDF into pgvector')
    parser.add_argument('--pdf', type=Path, default=Path('data/Final - Designed Viet Nam 2045 Full Report-En.pdf.pdf'))
    parser.add_argument('--manifest', type=Path, default=Path('benchmark/advanced/manifest.yaml'))
    parser.add_argument('--metadata-output', type=Path, default=Path('results/day7/ingest_metadata.json'))
    parser.add_argument('--batch-size', type=int, default=64)
    parser.add_argument('--dimensions', type=int, help='Optional output dimensions for embedding models that support it')
    args = parser.parse_args()

    load_dotenv(Path('.env'))
    base_url = os.environ.get('LLM_BASE_URL', DEFAULT_BASE_URL)
    api_key = os.environ.get('OPENROUTER_API_KEY') or os.environ.get('LLM_API_KEY')
    if not api_key:
        raise SystemExit('Set OPENROUTER_API_KEY or LLM_API_KEY in starter/.env')
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise SystemExit('Set DATABASE_URL in starter/.env')

    manifest = yaml.safe_load(args.manifest.read_text(encoding='utf-8'))
    source = manifest['source']
    if not args.pdf.is_file():
        raise FileNotFoundError(args.pdf)
    pdf_hash = hashlib.sha256(args.pdf.read_bytes()).hexdigest()
    if pdf_hash != source['snapshot_sha256']:
        raise ValueError(f'PDF SHA-256 mismatch: expected {source["snapshot_sha256"]}, got {pdf_hash}')

    reader = PdfReader(args.pdf)
    if len(reader.pages) != source['physical_page_count']:
        raise ValueError(f'Expected {source["physical_page_count"]} pages, got {len(reader.pages)}')
    pages = extract_pages(reader, source['counted_content_page_ranges'])
    empty = sorted(page for page, text in pages.items() if not text)
    if empty:
        print(f'warning: no text extracted from pages {empty}')

    model = embedding_model_name(os.environ, base_url)
    client = EmbeddingClient(base_url, api_key, model, args.batch_size)
    started = time.perf_counter()
    chunk_counts = {}
    stored_rows = []
    for strategy in STRATEGIES:
        rows = build_chunk_rows(pages, source['source_id'], source['source_path_or_url'], strategy)
        chunk_counts[f'{INDEX_PREFIX}{strategy}'] = len(rows)
        stored_rows.extend(rows)
    vectors = client.embed_all([row['content'] for row in stored_rows])
    dimensions = len(vectors[0])

    import psycopg

    with psycopg.connect(database_url, connect_timeout=10) as connection:
        store_chunks(connection, stored_rows, vectors)

    metadata = {
        'created_at': datetime.now(timezone.utc).isoformat(),
        'source_id': source['source_id'],
        'source_url': source['source_path_or_url'],
        'pdf_sha256': pdf_hash,
        'physical_page_count': len(reader.pages),
        'counted_content_page_count': len(pages),
        'counted_pdf_pages': sorted(pages),
        'embedding_model': model,
        'embedding_api_base': base_url,
        'embedding_dimensions': dimensions,
        'vector_store': 'PostgreSQL 16 + pgvector',
        'distance_metric': 'cosine',
        'index_prefix': INDEX_PREFIX,
        'chunking': {
            'A': {'method': 'fixed_size', 'size': FIXED_SIZE, 'overlap': FIXED_OVERLAP},
            'B': {'method': 'by_paragraph', 'max_size': PARAGRAPH_MAX_SIZE},
            'C': {'method': 'by_paragraph', 'max_size': PARAGRAPH_MAX_SIZE, 'filter': 'section at query time'},
        },
        'chunk_counts': chunk_counts,
        'stored_counts_verified': dict(chunk_counts),
        'embedding_seconds': round(client.usage['seconds'], 3),
        'embedding_requests': client.usage['requests'],
        'total_seconds': round(time.perf_counter() - started, 3),
    }
    args.metadata_output.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_output.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: metadata[k] for k in ('embedding_model', 'embedding_dimensions', 'chunk_counts', 'embedding_seconds')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
