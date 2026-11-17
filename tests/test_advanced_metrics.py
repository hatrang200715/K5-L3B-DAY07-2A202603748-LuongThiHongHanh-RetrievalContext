import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'starter'))
from advanced_metrics import group_report, question_passes

QUESTIONS = [
    {'id': 'a', 'split': 'test', 'group': 'table'},
    {'id': 'b', 'split': 'test', 'group': 'table'},
    {'id': 'c', 'split': 'test', 'group': 'insufficient_evidence'},
    {'id': 'd', 'split': 'test', 'group': 'chart'},
]
CASES = [
    {'id': 'a', 'split': 'test', 'answerable': True},
    {'id': 'b', 'split': 'test', 'answerable': True},
    {'id': 'c', 'split': 'test', 'answerable': False},
    {'id': 'd', 'split': 'test', 'answerable': True},
]

def trace(qid, status, citations=None):
    return {'query_id': qid, 'status': status, 'events': [{'event': 'search'}], 'citations': citations or []}

class AdvancedMetricsTests(unittest.TestCase):
    def test_group_pass_rates_and_errors(self):
        traces = [
            trace('a', 'answered', ['c1']),
            trace('b', 'error'),
            trace('c', 'abstain'),
            trace('d', 'answered', ['c9']),
        ]
        reviews = [
            {'query_id': 'a', 'answer_grade': 2, 'citation_support': [True]},
            {'query_id': 'c', 'citation_support': [], 'abstention_correct': True},
            {'query_id': 'd', 'answer_grade': 1, 'citation_support': [True]},
        ]
        report = group_report(QUESTIONS, CASES, traces, reviews)
        self.assertEqual(report['groups']['table'], {'pass': 1, 'total': 2, 'errors': 1})
        self.assertEqual(report['groups']['insufficient_evidence'], {'pass': 1, 'total': 1, 'errors': 0})
        self.assertEqual(report['groups']['chart'], {'pass': 0, 'total': 1, 'errors': 0})
        self.assertEqual(report['overall'], {'pass': 2, 'total': 4, 'rate_percent': 50.0})

    def test_unsupported_citation_or_wrong_abstention_fails(self):
        self.assertFalse(question_passes(
            CASES[0], trace('a', 'answered', ['c1', 'c2']),
            {'answer_grade': 2, 'citation_support': [True, False]}))
        self.assertFalse(question_passes(
            CASES[0], trace('a', 'abstain'), {'answer_grade': 0, 'citation_support': []}))
        self.assertFalse(question_passes(
            CASES[2], trace('c', 'answered', ['c1']),
            {'citation_support': [True], 'abstention_correct': False}))

    def test_missing_trace_review_or_case_raises(self):
        with self.assertRaises(ValueError):
            group_report(QUESTIONS[:1], CASES[:1], [], [])
        with self.assertRaises(ValueError):
            group_report(QUESTIONS[:1], CASES[:1], [trace('a', 'answered', ['c1'])], [])
        with self.assertRaises(ValueError):
            group_report(QUESTIONS, CASES[:3], [trace('a', 'answered', ['c1'])], [])
        with self.assertRaises(ValueError):
            group_report(QUESTIONS[:1], [{'id': 'a', 'split': 'test'}], [trace('a', 'answered', ['c1'])],
                         [{'query_id': 'a', 'answer_grade': 2, 'citation_support': [True]}])

if __name__ == '__main__':
    unittest.main()
