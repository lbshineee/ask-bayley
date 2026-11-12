"""Exercise the real Streamlit chat and draft widgets without a model server."""
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
import bayley


class CoreInterfaceTests(unittest.TestCase):
    def test_draft_edits_feedback_and_conversation_reset(self):
        root = Path(__file__).resolve().parents[1]
        with patch.dict(os.environ, {}, clear=True), \
             patch('bayley.answer_question', wraps=bayley.answer_question) as answer:
            at = AppTest.from_file(str(root / 'app.py'), default_timeout=15).run()
            self.assertEqual(len(at.exception), 0)
            at.chat_input[0].set_value('Canvas says access denied when I open my course.').run()
            at.chat_input[0].set_value('Please draft an email to them.').run()
            self.assertEqual(len(at.exception), 0)
            self.assertEqual(answer.call_count, 2)
            self.assertEqual(at.session_state['messages'][-1]['status'], 'draft')
            self.assertIn('Canvas says access denied', at.text_area(key='body_3_it').value)
            self.assertNotIn('Please draft an email', at.text_area(key='body_3_it').value)

            at.text_area(key='body_3_it').set_value('My reviewed Canvas request.').run()
            at.radio(key='vote_3').set_value('Helpful').run()
            self.assertEqual(at.text_area(key='body_3_it').value, 'My reviewed Canvas request.')
            self.assertEqual(answer.call_count, 2, 'Widget reruns must not generate another answer')

            next(b for b in at.button if b.label == 'New conversation').click().run()
            self.assertEqual(at.session_state['messages'], [])
            self.assertEqual(at.session_state['context'], {})
            self.assertEqual(at.session_state['feedback'], {})
            at.chat_input[0].set_value('The printer shows an error.').run()
            at.chat_input[0].set_value('Draft an email to IT.').run()
            self.assertEqual(len(at.exception), 0)
            new_body = at.text_area(key='body_3_it').value
            self.assertIn('The printer shows an error.', new_body)
            self.assertNotIn('Canvas', new_body)
            self.assertEqual(answer.call_count, 4)


if __name__ == '__main__':
    unittest.main()
