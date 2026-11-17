"""Per-group pass rates for the advanced benchmark from human-reviewed labels."""
import argparse
import json
from pathlib import Path

from agent_metrics import aggregate

GROUP_ORDER = ('table', 'image_diagram', 'chart', 'multi_hop', 'text', 'insufficient_evidence')


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def question_passes(case, trace, review):
    if trace.get('status') == 'error':
        return False
    if case['answerable']:
        support = review.get('citation_support')
        return (
            trace.get('status') == 'answered'
            and review.get('answer_grade') == 2
            and isinstance(support, list)
            and bool(support)
            and all(support)
        )
    return trace.get('status') == 'abstain' and review.get('abstention_correct') is True


def group_report(questions, cases, traces, reviews):
    trace_by_id = {t['query_id']: t for t in traces}
    review_by_id = {r['query_id']: r for r in reviews}
    case_by_id = {c['id']: c for c in cases}
    question_ids = {q['id'] for q in questions}
    if question_ids != set(case_by_id):
        raise ValueError('question ID và case ID không khớp trong split')
    groups = {}
    for question in questions:
        qid = question['id']
        trace = trace_by_id.get(qid)
        if trace is None:
            raise ValueError(f'{qid}: thiếu trace')
        case = case_by_id[qid]
        if type(case.get('answerable')) is not bool:
            raise ValueError(f'{qid}: thiếu answerable boolean')
        entry = groups.setdefault(question['group'], {'pass': 0, 'total': 0, 'errors': 0})
        entry['total'] += 1
        if trace.get('status') == 'error':
            entry['errors'] += 1
            continue
        review = review_by_id.get(qid)
        if review is None:
            raise ValueError(f'{qid}: thiếu nhãn audit')
        if question_passes(case, trace, review):
            entry['pass'] += 1
    overall_pass = sum(g['pass'] for g in groups.values())
    overall_total = sum(g['total'] for g in groups.values())
    return {
        'groups': {name: groups[name] for name in GROUP_ORDER if name in groups},
        'overall': {
            'pass': overall_pass,
            'total': overall_total,
            'rate_percent': overall_pass / overall_total * 100 if overall_total else None,
        },
    }


def main():
    parser = argparse.ArgumentParser(description='Tổng hợp tỉ lệ đạt theo nhóm cho benchmark advanced')
    parser.add_argument('--questions', type=Path, required=True)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--traces', type=Path, required=True)
    parser.add_argument('--reviews', type=Path, required=True)
    parser.add_argument('--split', choices=('dev', 'test'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    questions = [q for q in load(args.questions)['questions'] if q['split'] == args.split]
    cases = [c for c in load(args.cases) if c.get('split') == args.split]
    traces = load(args.traces)
    reviews = load(args.reviews)
    if not cases:
        raise ValueError('không có case trong split')
    quality = aggregate(cases, traces, reviews)
    report = {'split': args.split, **group_report(questions, cases, traces, reviews), 'quality': quality}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
