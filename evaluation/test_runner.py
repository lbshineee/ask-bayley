"""Checks for the evaluation tool itself; separate from application regressions."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import run_evaluation as runner


class EvaluationRunnerTests(unittest.TestCase):
    def test_suite_has_distinct_cases_and_all_categories(self):
        cases=runner.load_cases(runner.ROOT/'evaluation/cases.json')
        self.assertEqual(len(cases),120)
        self.assertEqual(len({c['id'] for c in cases}),120)
        self.assertEqual(len({json.dumps(c['turns'],sort_keys=True) for c in cases}),120)
        self.assertEqual(len({c['category'] for c in cases}),10)
        self.assertEqual(sum(len(c['turns']) for c in cases),148)

    def test_smoke_suite_covers_all_categories(self):
        cases=runner.load_cases(runner.ROOT/'evaluation/cases.json',smoke=True)
        self.assertEqual(len(cases),12)
        self.assertEqual(len({c['category'] for c in cases}),10)

    def test_wrong_evidence_is_not_a_pass(self):
        reply={'status':'answered','mode':'Keyword retrieval','entries':[{'id':'hours'}]}
        self.assertTrue(runner.check_expectations(reply,{'allowed_evidence':['food']},0,''))

    def test_missing_evidence_and_stale_context_are_reported(self):
        reply={'status':'answered','mode':'Keyword retrieval','entries':[],'context':{'season':'spring'}}
        self.assertEqual(len(runner.check_expectations(reply,{'evidence_all':['it'],'context_absent':['season']},0,'')),2)

    def test_early_route_network_use_is_reported(self):
        reply={'status':'conversation','mode':'Safety boundary','entries':[]}
        self.assertTrue(runner.check_expectations(reply,{'api_calls_max':0},1,''))

    def test_invalid_external_endpoint_is_rejected_before_request(self):
        with patch.dict(os.environ,{'BAYLEY_WEBUI_URL':'https://example.com','BAYLEY_WEBUI_API_KEY':'not-real'}),patch.object(runner,'urlopen') as call:
            with self.assertRaises(ValueError):runner.preflight('qwen3:8b')
            call.assert_not_called()

    def test_offline_run_never_uses_or_records_key_and_preserves_output(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'BAYLEY_WEBUI_API_KEY':'SECRET_TEST_VALUE'}),contextlib.redirect_stdout(io.StringIO()):
            path=Path(tmp)/'run'
            runner.main(['--mode','offline','--limit','12','--output',str(path)])
            self.assertEqual(os.environ['BAYLEY_WEBUI_API_KEY'],'SECRET_TEST_VALUE')
            summary=json.loads((path/'summary.json').read_text())
            self.assertEqual(summary['model_requests'],0)
            self.assertIsNone(summary['answer_accuracy'])
            self.assertIsNone(summary['latency_by_path'])
            self.assertNotIn('SECRET_TEST_VALUE',''.join(p.read_text() for p in path.iterdir()))
            with self.assertRaises(FileExistsError):runner.main(['--mode','offline','--limit','1','--output',str(path)])

    def test_draft_export_includes_original_problem(self):
        sources,entries=runner.bayley.load_data()
        it=next(e for e in entries if e['id']=='it')
        rendered,urls=runner.visible_answer({'status':'draft','text':'Review your draft.','entries':[it],
            'draft_question':'Canvas says access denied.'},sources)
        self.assertIn('Canvas says access denied.',rendered)
        self.assertIn('Editable draft to AskIT@sfbu.edu',rendered)
        self.assertTrue(urls)


if __name__=='__main__':unittest.main()
