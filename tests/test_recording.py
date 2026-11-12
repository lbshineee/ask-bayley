"""Run the actual six-message demo through the backend and Streamlit widgets."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import bayley
from scripts.check_recording import QUESTIONS, verify


class RecordingTests(unittest.TestCase):
    def test_exact_six_turn_sequence(self):
        _, entries = bayley.load_data()
        context, history = {}, []
        with patch.dict(os.environ, {'BAYLEY_WEBUI_API_KEY':''}):
            for i, q in enumerate(QUESTIONS):
                reply = bayley.answer_question(q, entries, context, False, history)
                verify(i, reply)
                context = reply['context']
                history.extend([{'role':'user','text':q},{'role':'assistant','text':reply['text']}])

    def test_guide_with_configured_model_and_generation_error(self):
        _, entries = bayley.load_data()
        with patch.dict(os.environ, {'BAYLEY_WEBUI_API_KEY':'test'}), \
             patch('bayley.api', side_effect=TimeoutError):
            r = bayley.answer_question(QUESTIONS[0], entries, {})
        verify(0, r)
        self.assertNotIn('diagnostic', r)

    def test_real_streamlit_six_turns_and_reset(self):
        from streamlit.testing.v1 import AppTest
        with patch.dict(os.environ, {'BAYLEY_WEBUI_API_KEY':''}):
            app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'), default_timeout=20).run()
            for i, q in enumerate(QUESTIONS):
                app.chat_input[0].set_value(q).run()
                self.assertFalse(app.exception, str(app.exception))
                verify(i, app.session_state['messages'][-1])
            self.assertIn(QUESTIONS[4], app.text_area(key='body_11_it').value)
            self.assertEqual(app.text_input(key='to_11_it').value, 'AskIT@sfbu.edu')
            rendered='\n'.join(m.value for m in app.markdown)
            self.assertNotIn('(None)', rendered)
            self.assertIn('user-verified', rendered)
            self.assertIn('Entrance Health Requirements', rendered)
            next(b for b in app.button if b.label=='New conversation').click().run()
            self.assertEqual(app.session_state['messages'], [])
            app.chat_input[0].set_value('Is there anything I should know?').run()
            self.assertEqual(app.session_state['messages'][-1]['status'], 'onboarding')


if __name__ == '__main__': unittest.main()
