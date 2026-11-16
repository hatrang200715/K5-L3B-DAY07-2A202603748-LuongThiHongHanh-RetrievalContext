"""Run the real OpenRouter agent against the Day 7 dev retrieval strategies."""
import argparse
import base64
import json
import math
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psycopg
from dotenv import load_dotenv

from agentic import run_agent


OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
STRATEGIES = ('A', 'B', 'C')
VISUAL_GROUPS = {'table', 'image_diagram', 'chart', 'multi_hop'}
SYSTEM_PROMPT = """You answer questions using only evidence retrieved from the supplied report.
Use search whenever evidence is needed. You may search again if the current
context is incomplete. If the report does not establish the answer, abstain.
Do not guess. Every factual claim in a final answer must be supported by the
context and retrieved page images. When page images are provided, inspect charts,
tables, legends and maps directly. Each citation must use the exact chunk ID in
square brackets and must correspond to retrieved evidence.
After retrieval, answer immediately if the evidence is sufficient. If another
search is needed, use a materially different query; never repeat a search.
Finish with the final_answer tool, including every cited chunk ID."""

TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'search',
            'description': 'Search the report for evidence relevant to the question.',
            'parameters': {
                'type': 'object',
                'properties': {'query': {'type': 'string'}},
                'required': ['query'],
                'additionalProperties': False,
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'final_answer',
            'description': 'Answer from retrieved evidence or abstain when evidence is insufficient.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'answer': {'type': 'string'},
                    'citations': {'type': 'array', 'items': {'type': 'string'}},
                },
                'required': ['answer', 'citations'],
                'additionalProperties': False,
            },
        },
    },
]


class OpenRouter:
    def __init__(self, api_key, model, embedding_model, visual_pages_dir=None):
        self.api_key = api_key
        self.model = model
        self.embedding_model = embedding_model
        self.visual_pages_dir = visual_pages_dir
        self.include_visual_evidence = True
        self.usage = {
            'chat_requests': 0,
            'embedding_requests': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'reported_cost_usd': 0.0,
            'cost_reporting_missing': 0,
        }
        self.decisions = []

    def _request(self, endpoint, payload):
        request = Request(
            f'{OPENROUTER_BASE_URL}/{endpoint}',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://github.com/hatrang200715/K5-L3B-DAY07-2A202603748-LuongThiHongHanh-RetrievalContext',
                'X-Title': 'Day 7 retrieval-context benchmark',
            },
            method='POST',
        )
        try:
            with urlopen(request, timeout=90) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')[:1000]
            raise RuntimeError(f'OpenRouter HTTP {exc.code}: {detail}') from exc
        except URLError as exc:
            raise RuntimeError(f'OpenRouter connection error: {exc.reason}') from exc

    def _record_usage(self, response, request_type):
        self.usage[f'{request_type}_requests'] += 1
        usage = response.get('usage') or {}
        self.usage['prompt_tokens'] += int(usage.get('prompt_tokens') or 0)
        self.usage['completion_tokens'] += int(usage.get('completion_tokens') or 0)
        cost = usage.get('cost', response.get('cost'))
        if cost is None:
            self.usage['cost_reporting_missing'] += 1
        else:
            self.usage['reported_cost_usd'] += float(cost)

    def embed(self, text):
        response = self._request('embeddings', {'model': self.embedding_model, 'input': text})
        self._record_usage(response, 'embedding')
        try:
            vector = response['data'][0]['embedding']
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError('OpenRouter embeddings response has no vector') from exc
        if not isinstance(vector, list) or not vector or any(
            not isinstance(value, (int, float)) or not math.isfinite(value) for value in vector
        ):
            raise ValueError('OpenRouter returned an invalid embedding vector')
        return vector

    def decide(self, question, history):
        messages = [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': f'Question: {question}'},
        ]
        if history:
            entry = history[-1]
            query_lines = '\n'.join(f'- {query}' for query in entry['queries'])
            content = [{
                'type': 'text',
                'text': (
                    f'Previous searches:\n{query_lines}\n\n'
                    f'Current retrieved text context:\n{entry["context"] or "(no context fits the budget)"}'
                ),
            }]
            if self.visual_pages_dir and self.include_visual_evidence:
                for page_number in entry.get('visual_pages', [])[:2]:
                    path = self.visual_pages_dir / f'page-{page_number:03}.png'
                    if not path.is_file():
                        raise FileNotFoundError(f'Visual evidence page is missing: {path}')
                    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
                    content.append({
                        'type': 'text',
                        'text': f'Visual evidence: source PDF physical page {page_number}.',
                    })
                    content.append({
                        'type': 'image_url',
                        'image_url': {'url': f'data:image/png;base64,{encoded}'},
                    })
            messages.append({'role': 'user', 'content': content})
        response = self._request('chat/completions', {
            'model': self.model,
            'temperature': 0,
            'max_tokens': 700,
            'parallel_tool_calls': False,
            'tools': TOOLS,
            'tool_choice': 'auto',
            'messages': messages,
        })
        self._record_usage(response, 'chat')
        try:
            message = response['choices'][0]['message']
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError('OpenRouter chat response has no assistant message') from exc
        calls = message.get('tool_calls') or []
        if not calls:
            raise ValueError('Model returned no tool call; expected search or final_answer')
        call = calls[0]['function']
        try:
            arguments = json.loads(call['arguments'])
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError('Model returned invalid tool arguments') from exc
        if call.get('name') == 'search':
            action = {'action': 'search', **arguments}
        elif call.get('name') == 'final_answer':
            action = {'action': 'answer', **arguments}
            answer = action.get('answer')
            citations = action.get('citations')
            if isinstance(answer, str) and isinstance(citations, list):
                for citation in citations:
                    marker = f'[{citation}]' if isinstance(citation, str) else None
                    if marker and marker not in answer:
                        answer = f'{answer.rstrip()} {marker}'
                action['answer'] = answer
        else:
            raise ValueError(f"Model returned unsupported tool: {call.get('name')}")
        decision = {'tool': call['name'], 'arguments': arguments}
        if history:
            decision['context'] = history[-1]['context']
            decision['context_ids'] = history[-1]['context_ids']
            decision['visual_pages'] = history[-1].get('visual_pages', [])
        self.decisions.append(decision)
        return action


class PgVectorRetriever:
    def __init__(self, connection, openrouter, strategy, dimensions, visual_pages_dir=None):
        self.connection = connection
        self.openrouter = openrouter
        self.strategy = strategy
        self.dimensions = dimensions
        self.visual_pages_dir = visual_pages_dir
        self.embedding_cache = {}
        self.embedding_seconds = 0.0
        self.search_seconds = []
        self.search_events = []

    def search(self, query, *, filters=None, top_k=3):
        started = time.perf_counter()
        if query not in self.embedding_cache:
            embed_started = time.perf_counter()
            vector = self.openrouter.embed(query)
            self.embedding_seconds += time.perf_counter() - embed_started
            if len(vector) != self.dimensions:
                raise ValueError(
                    f'Embedding dimension mismatch: expected {self.dimensions}, got {len(vector)}'
                )
            self.embedding_cache[query] = vector
        vector = self.embedding_cache[query]
        vector_literal = '[' + ','.join(format(value, '.9g') for value in vector) + ']'
        where = ['strategy = %s']
        params = [f'day7_{self.strategy}']
        if filters:
            if set(filters) != {'section'} or not isinstance(filters['section'], str):
                raise ValueError('Only the benchmark section filter is supported')
            where.append("metadata ->> 'section' = %s")
            params.append(filters['section'])
        params.extend([vector_literal, top_k])
        sql = f"""
            SELECT chunk_id, document_id, source, page, content, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM day6_chunks
            WHERE {' AND '.join(where)}
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        """
        # The vector is supplied twice: once for the displayed score and once for ranking.
        params = [vector_literal, *params[:-2], vector_literal, top_k]
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        elapsed = time.perf_counter() - started
        self.search_seconds.append(elapsed)
        results = [
            {
                'id': row[0],
                'source_id': row[1],
                'source': row[2],
                'page': row[3],
                'text': row[4],
                'metadata': row[5] or {},
                'score': float(row[6]),
                **({'visual_page': row[3]} if self.visual_pages_dir else {}),
            }
            for row in rows
        ]
        self.search_events.append({
            'event': 'search',
            'query': query,
            'filter': filters,
            'results': results,
            'elapsed_seconds': elapsed,
        })
        return results


def _embedding_model(config):
    model = config.get('EMBEDDING_MODEL', 'text-embedding-3-small').strip()
    if model.startswith('openrouter:'):
        model = model.removeprefix('openrouter:')
    if '/' not in model:
        model = f'openai/{model}'
    return model


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='Run the real agent on Day 7 benchmark strategies')
    parser.add_argument('--model', required=True, help='OpenRouter chat model ID')
    parser.add_argument('--split', choices=('dev', 'test'), default='dev')
    parser.add_argument('--strategies', nargs='+', choices=STRATEGIES, default=list(STRATEGIES))
    parser.add_argument('--questions', type=Path, default=Path('benchmark/day7/questions.json'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--top-k', type=int, default=3)
    parser.add_argument('--max-searches', type=int, default=4)
    parser.add_argument('--budget-chars', type=int, default=3000)
    parser.add_argument('--visual-index', type=Path)
    args = parser.parse_args()
    if min(args.top_k, args.max_searches, args.budget_chars) < 1:
        parser.error('top-k, max-searches, and budget-chars must be positive')

    load_dotenv(Path('.env'))
    api_key = os.environ.get('OPENROUTER_API_KEY')
    database_url = os.environ.get('DATABASE_URL')
    if not api_key or not database_url:
        parser.error('OPENROUTER_API_KEY and DATABASE_URL are required in starter/.env')

    ingest_path = Path('results/day7/ingest_metadata.json')
    ingest = json.loads(ingest_path.read_text(encoding='utf-8'))
    dimensions = int(ingest['embedding_dimensions'])
    embedding_model = _embedding_model(os.environ)
    question_data = json.loads(args.questions.read_text(encoding='utf-8'))
    questions = question_data.get('questions') if isinstance(question_data, dict) else question_data
    if not isinstance(questions, list):
        raise ValueError('Question file must contain a question list')
    selected = [question for question in questions if question.get('split') == args.split]
    expected_count = question_data.get('expected_counts', {}).get(
        args.split, {'dev': 17, 'test': 7}[args.split]
    )
    if len(selected) != expected_count:
        raise ValueError(f'Expected {expected_count} Day 7 {args.split} questions, found {len(selected)}')
    if any('gold' in question or 'answerability' in question for question in selected):
        raise ValueError('Public questions must not contain gold or answerability labels')
    visual_pages_dir = None
    if args.visual_index:
        visual_index_path = args.visual_index / 'index.json'
        visual_index = json.loads(visual_index_path.read_text(encoding='utf-8'))
        if visual_index['source_pdf_sha256'] != ingest['pdf_sha256']:
            raise ValueError('Visual index and vector index refer to different source PDFs')
        visual_pages_dir = args.visual_index / 'pages'

    output = args.output or Path(
        f'results/day7/agent_{args.split}_'
        + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    )
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f'Output directory is not empty: {output}')
    output.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc).isoformat()
    run_started = time.perf_counter()
    traces = []
    strategy_summaries = {}
    with psycopg.connect(database_url, connect_timeout=10) as connection:
        for strategy in args.strategies:
            provider = OpenRouter(api_key, args.model, embedding_model, visual_pages_dir)
            retriever = PgVectorRetriever(
                connection, provider, strategy, dimensions, visual_pages_dir
            )
            strategy_started = time.perf_counter()
            strategy_traces = []
            for question in selected:
                provider.include_visual_evidence = question.get('group') in VISUAL_GROUPS
                filters = question.get('filter') if strategy == 'C' else None
                case_started = time.perf_counter()
                calls_before = dict(provider.usage)
                decisions_before = len(provider.decisions)
                searches_before = len(retriever.search_events)
                try:
                    result = run_agent(
                        question['question'],
                        provider,
                        retriever,
                        filters=filters,
                        max_searches=args.max_searches,
                        top_k=args.top_k,
                        budget=args.budget_chars,
                    )
                    trace = {
                        'query_id': question['id'],
                        'split': args.split,
                        'strategy': strategy,
                        'index_strategy': f'day7_{strategy}',
                        'question': question['question'],
                        'group': question.get('group'),
                        'question_type': question.get('type'),
                        'filter': filters,
                        **result,
                    }
                except Exception as exc:
                    trace = {
                        'query_id': question['id'],
                        'split': args.split,
                        'strategy': strategy,
                        'index_strategy': f'day7_{strategy}',
                        'question': question['question'],
                        'group': question.get('group'),
                        'question_type': question.get('type'),
                        'filter': filters,
                        'status': 'error',
                        'answer': None,
                        'citations': [],
                        'events': retriever.search_events[searches_before:],
                        'error': {'type': type(exc).__name__, 'message': str(exc)},
                    }
                trace['elapsed_seconds'] = time.perf_counter() - case_started
                trace['model_tool_calls'] = provider.decisions[decisions_before:]
                trace['usage'] = {
                    key: provider.usage[key] - calls_before[key] for key in provider.usage
                }
                strategy_traces.append(trace)
                traces.append(trace)
                print(f"{strategy} {question['id']}: {trace['status']}", flush=True)

            elapsed = time.perf_counter() - strategy_started
            statuses = {status: sum(t['status'] == status for t in strategy_traces)
                        for status in ('answered', 'abstain', 'error')}
            reported_cost = provider.usage['reported_cost_usd']
            strategy_summaries[strategy] = {
                'index_strategy': f'day7_{strategy}',
                'question_count': len(strategy_traces),
                'statuses': statuses,
                'elapsed_seconds': elapsed,
                'mean_case_seconds': statistics.mean(t['elapsed_seconds'] for t in strategy_traces),
                'retrieval_calls': sum(
                    event.get('event') == 'search'
                    for trace in strategy_traces for event in trace.get('events', [])
                ),
                'embedding_requests': provider.usage['embedding_requests'],
                'chat_requests': provider.usage['chat_requests'],
                'prompt_tokens': provider.usage['prompt_tokens'],
                'completion_tokens': provider.usage['completion_tokens'],
                'reported_cost_usd': reported_cost,
                'cost_reporting_missing_requests': provider.usage['cost_reporting_missing'],
                'embedding_seconds': retriever.embedding_seconds,
                'mean_retrieval_seconds': statistics.mean(retriever.search_seconds)
                if retriever.search_seconds else None,
            }

    run = {
        'started_at': started_at,
        'completed_at': datetime.now(timezone.utc).isoformat(),
        'split': args.split,
        'model': args.model,
        'provider': 'OpenRouter',
        'embedding_model': embedding_model,
        'embedding_dimensions': dimensions,
        'vector_store': ingest['vector_store'],
        'corpus_sha256': ingest['pdf_sha256'],
        'strategies': args.strategies,
        'question_count_per_strategy': len(selected),
        'agent_parameters': {
            'top_k': args.top_k,
            'max_searches': args.max_searches,
            'context_budget': args.budget_chars,
            'context_budget_unit': 'characters',
            'temperature': 0,
            'answer_max_tokens': 700,
            'filter_policy': 'Only strategy C applies the explicit question section filter.',
            'visual_index': str(args.visual_index) if args.visual_index else None,
            'visual_evidence_policy': (
                'Attach up to two full source pages for table, chart, image/diagram, and multi-hop questions.'
                if visual_pages_dir else 'Disabled'
            ),
        },
        'total_elapsed_seconds': time.perf_counter() - run_started,
        'strategy_summaries': strategy_summaries,
    }
    _write_json(output / 'traces.json', traces)
    _write_json(output / 'summary.json', strategy_summaries)
    _write_json(output / 'run.json', run)
    print(json.dumps({'output': str(output), 'summary': strategy_summaries},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
