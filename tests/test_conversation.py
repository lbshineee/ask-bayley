import os
import unittest
from unittest.mock import patch
import bayley
class ConversationTests(unittest.TestCase):
 def setUp(self):
  _,self.entries=bayley.load_data();self.env=patch.dict(os.environ,{},clear=True);self.env.start()
 def tearDown(self):self.env.stop()
 def payload(self,text='Nick Ladany is listed as SFBU’s president.'):
  return {'paragraphs':[{'text':text,'evidence':[{'id':'president','quote':self.entries[0]['text']}]}]}
 def test_identity(self):
  r=bayley.answer_question('hi who are you',self.entries,{},False)
  self.assertEqual(r['status'],'conversation');self.assertIn('Bayley',r['text']);self.assertFalse(r['entries'])
 def test_natural_reply_and_history(self):
  with patch.dict(os.environ,{'BAYLEY_WEBUI_API_KEY':'test'}),patch('bayley.completion',return_value=self.payload()) as call:
   r=bayley.answer_question('Who is president?',self.entries,{},False,[{'role':'user','text':'Tell me about leadership'}])
   self.assertEqual(r['paragraphs'][0]['evidence_ids'],['president']);self.assertIn('Tell me about leadership',str(call.call_args))
 def test_invalid_numbers(self):
  with self.assertRaises(ValueError):bayley.validate_answer(self.payload('Nick has been president since 1900.'),self.entries)
 def test_invented_citation(self):
  p=self.payload();p['paragraphs'][0]['evidence'][0]['id']='made-up'
  with self.assertRaises(ValueError):bayley.validate_answer(p,self.entries)
 def test_missing_evidence(self):
  with patch.dict(os.environ,{'BAYLEY_WEBUI_API_KEY':'test'}),patch('bayley.completion',return_value={'clarification':'Which facility do you mean?'}) as call:
   r=bayley.answer_question('Where is the swimming pool?',self.entries,{},False)
   self.assertEqual(r['status'],'missing');self.assertIn('Which facility',r['text']);call.assert_called_once()
 def test_invalid_reply_fallback(self):
  with patch.dict(os.environ,{'BAYLEY_WEBUI_API_KEY':'test'}),patch('bayley.completion',return_value=self.payload('Call invented@invalid.example.')):
   r=bayley.answer_question('Who is president?',self.entries,{},False)
   self.assertFalse(r['paragraphs']);self.assertIn('fallback',r['mode'])
 def test_followup(self):
  a=bayley.answer_question('Where do I get Canvas help?',self.entries,{},False)
  b=bayley.answer_question('How do I contact them?',self.entries,a['context'],False)
  self.assertIn('it',[e['id'] for e in b['entries']])
