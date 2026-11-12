"""Regression coverage for failures found during the pre-submission review."""
import os
import unittest
from unittest.mock import patch

import bayley
from actions import draft


class CoreFixTests(unittest.TestCase):
    def setUp(self):
        self.sources, self.entries = bayley.load_data()
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def ask(self, question, context=None):
        return bayley.answer_question(question, self.entries, context or {}, False)

    def ids(self, reply):
        return [e['id'] for e in reply['entries']]

    def spring(self):
        return self.ask('When do standard-semester classes start in Spring 2027?')

    def canvas(self):
        return self.ask('Canvas says access denied when I open my course.')

    def test_start_ticket_does_not_ask_for_term(self):
        for q in ['How do I start an IT ticket?', 'Who can help me add a printer?',
                  'When can IT help me add a printer?', 'I need IT support']:
            with self.subTest(q=q):
                r = self.ask(q)
                self.assertEqual(self.ids(r), ['it'])
                self.assertFalse(r['show_calendar_context'])

    def test_help_word_does_not_add_unrelated_contacts(self):
        self.assertEqual(self.ids(self.ask('I cannot log into Canvas. Who can help?')), ['it'])

    def test_study_paraphrases_use_general_generation(self):
        for q in ['How do I prepare for my exams?', 'Help me prepare for the exam.',
                  'How should I study for my finals?']:
            with self.subTest(q=q), patch.dict(os.environ, {'BAYLEY_WEBUI_API_KEY':'test'}), \
                 patch('bayley.general_reply', return_value='General study guidance: review one topic at a time.') as model, \
                 patch('bayley.retrieve', side_effect=AssertionError('Must not retrieve a calendar')):
                r = self.ask(q)
                model.assert_called_once()
                self.assertEqual(r['mode'], 'General guidance · qwen3:8b')

    def test_exam_dates_still_use_calendar(self):
        r = self.ask('When are final exams in Spring 2027 for the standard semester?')
        self.assertEqual(self.ids(r), ['spring-2027-finals'])

    def test_start_retrieves_only_start_evidence(self):
        self.assertEqual(self.ids(self.spring()), ['spring-2027-start'])

    def test_term_substitution_then_program_confirmation(self):
        a = self.spring()
        b = self.ask('What about Summer 2027?', a['context'])
        self.assertEqual(b['context']['season'], 'summer')
        self.assertNotIn('program', b['context'])
        self.assertIn('standard semester', b['text'])
        c = self.ask('standard semester', b['context'])
        self.assertEqual(self.ids(c), ['summer-2027-start'])
        d = self.ask('And when can I drop?', c['context'])
        self.assertEqual(self.ids(d), ['summer-2027-drop'])

    def test_explicit_program_term_substitution(self):
        r = self.ask('What about Summer 2027 standard semester?', self.spring()['context'])
        self.assertEqual(self.ids(r), ['summer-2027-start'])

    def test_term_without_year_does_not_guess_year(self):
        r = self.ask('What about summer?', self.spring()['context'])
        self.assertNotIn('year', r['context'])
        self.assertIn('Which year', r['text'])

    def test_new_term_unsupported_without_network(self):
        with patch('bayley.retrieve', side_effect=AssertionError('Coverage checked before retrieval')):
            r = self.ask('What about Fall 2028?', self.spring_context())
        self.assertEqual(r['status'], 'missing_calendar')
        self.assertIn('Fall 2028', r['text'])
        self.assertNotIn('program', r['context'])

    def spring_context(self):
        return {'season':'spring','year':'2027','program':'standard semester',
                'active_topic':'calendar','calendar_event':'start'}

    def test_topic_switch_discards_pending_calendar(self):
        a = self.ask('When do classes start?')
        b = self.ask('Actually, who chairs business?', a['context'])
        self.assertIn('business-chair', self.ids(b))
        self.assertNotIn('pending_question', b['context'])
        self.assertNotIn('calendar_event', b['context'])
        c = self.ask('Spring 2027', b['context'])
        self.assertIn('What would you like to know', c['text'])
        self.assertFalse(c['entries'])

    def test_generic_followup_after_switch_does_not_reuse_calendar(self):
        a = self.spring()
        b = self.ask('Where do I get Canvas help?', a['context'])
        c = self.ask('How do I contact them?', b['context'])
        self.assertEqual(self.ids(c), ['it'])
        self.assertNotIn('season', c['context'])

    def test_preparation_topic_clears_calendar(self):
        r = self.ask('How do I prepare for my exams?', self.spring_context())
        self.assertNotIn('season', r['context'])
        self.assertNotIn('pending_question', r['context'])

    def test_one_year_with_missing_term(self):
        r = self.ask('When do classes start in 2027?')
        self.assertIn('Which term in 2027', r['text'])

    def test_multiple_terms_asks_to_split(self):
        r = self.ask('When do classes start in Spring and Summer 2027?')
        self.assertIn('one term', r['text'])
        self.assertFalse(r['entries'])

    def test_draft_contains_original_problem(self):
        for q in ['Please draft an email to them.', 'Write an email to IT.']:
            with self.subTest(q=q), patch('bayley.completion', side_effect=AssertionError('Template needs no model')):
                r = self.ask(q, self.canvas()['context'])
                self.assertEqual(r['status'], 'draft')
                self.assertEqual(self.ids(r), ['it'])
                subject, body = draft(r['draft_question'], r['entries'][0])
                self.assertIn('Canvas says access denied when I open my course.', body)
                self.assertNotIn(q, body)
                self.assertIn('[fill in]', body)

    def test_draft_retains_additional_error_detail(self):
        a = self.ask('I cannot log into Canvas.')
        b = self.ask('It says access denied.', a['context'])
        c = self.ask('Please draft an email to IT.', b['context'])
        self.assertEqual(c['status'], 'draft')
        self.assertIn('I cannot log into Canvas.', c['draft_question'])
        self.assertIn('It says access denied.', c['draft_question'])

    def test_draft_without_problem_asks_for_it(self):
        r = self.ask('Please draft an email to IT.')
        self.assertEqual(r['status'], 'clarification')
        self.assertIn('problem', r['text'])
        self.assertNotIn('draft_question', r)

    def test_inline_draft_uses_supplied_problem(self):
        r = self.ask('Draft an email to IT: Canvas shows access denied.')
        self.assertEqual(r['status'], 'draft')
        self.assertEqual(r['draft_question'], 'Canvas shows access denied.')

    def test_unknown_target_does_not_reuse_it(self):
        r = self.ask('Draft an email to Professor Example.', self.canvas()['context'])
        self.assertFalse(r['entries'])
        self.assertEqual(r['status'], 'clarification')

    def test_new_recipient_does_not_inherit_old_problem(self):
        r = self.ask('Draft an email to housing.', self.canvas()['context'])
        self.assertEqual(r['status'], 'clarification')
        self.assertNotIn('draft_question', r)

    def test_explicit_recipient_beats_inline_service_reference(self):
        r = self.ask('Draft an email to housing: Please explain where to find the housing guide in Canvas.')
        self.assertEqual(self.ids(r), ['housing'])

    def test_topic_switch_clears_draft_context(self):
        a = self.canvas()
        b = self.ask('Who is SFBU president?', a['context'])
        c = self.ask('Draft an email to them.', b['context'])
        self.assertEqual(c['status'], 'clarification')
        self.assertFalse(c['entries'])

    def test_failed_generation_still_offers_original_problem(self):
        with patch.dict(os.environ, {'BAYLEY_WEBUI_API_KEY':'test'}), \
             patch('bayley.completion', side_effect=TimeoutError):
            a = self.canvas()
        self.assertIn('source-note fallback', a['mode'])
        self.assertEqual(self.ask('Draft an email to them.', a['context'])['status'], 'draft')

    def test_resolved_term_reaches_model_without_old_term(self):
        e = next(e for e in self.entries if e['id']=='summer-2027-start')
        with patch.dict(os.environ, {'BAYLEY_WEBUI_API_KEY':'test'}), \
             patch('bayley.completion', return_value={'paragraphs':[{'text':e['text'], 'evidence':[{'id':e['id'],'quote':e['text']}]}]}) as model:
            r = self.ask('What about Summer 2027 standard semester?', self.spring_context())
            self.assertEqual(self.ids(r), [e['id']])
            payload = model.call_args.args[0][-1]['content']
            self.assertNotIn('spring', payload.casefold())
            self.assertIn('summer', payload.casefold())


if __name__ == '__main__':
    unittest.main()
