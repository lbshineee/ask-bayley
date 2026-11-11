import copy
import json
import os
import unittest
from unittest.mock import patch
import bayley
from actions import draft,mailto

class EvidenceTests(unittest.TestCase):
 def setUp(self):
  self.sources,self.entries=bayley.load_data()
  self.env=patch.dict(os.environ,{},clear=True);self.env.start()
 def tearDown(self):self.env.stop()
 def ask(self,q,ctx=None):return bayley.answer_question(q,self.entries,ctx or {},semantic=False)
 def test_president_typo(self):
  r=self.ask('who is the presendate of sfbu');self.assertEqual(r['entries'][0]['id'],'president')
 def test_context_and_program(self):
  a=self.ask('When do classes start?');self.assertIn('term and year',a['text'])
  b=self.ask('Spring 2027',a['context']);self.assertIn('standard semester',b['text'])
  c=self.ask('standard semester',b['context']);self.assertEqual(c['entries'][0]['id'],'spring-2027-start')
  d=self.ask('And when can I drop?',c['context']);self.assertEqual(d['entries'][0]['id'],'spring-2027-drop')
 def test_proplus_does_not_get_standard_dates(self):
  r=self.ask('When do Pro+ classes start Spring 2027?');self.assertFalse(any(e.get('topic')=='calendar' for e in r['entries']))
 def test_unknown(self):self.assertEqual(self.ask('Where is the swimming pool?')['status'],'missing')
 def test_conflict(self):
  other=copy.deepcopy(self.entries[0]);other['id']='conflicting-president';other['fact_value']='Different person';other['text']='Another person is president.'
  r=bayley.answer_question('Who is president?',self.entries+[other],{},False);self.assertEqual(r['status'],'conflict')
 def test_expired(self):
  old=copy.deepcopy(self.entries[0]);old['effective_to']='2020-01-01'
  self.assertFalse(bayley.retrieve('president',[old],{},False)[0])
 def test_citation_rejects_fabricated_text(self):
  with self.assertRaises(ValueError):bayley.validate_claims({'claims':[{'evidence_id':'president','quote':'SFBU president is fictional.'}]},self.entries)
 def test_citation_valid_preserves_full_note(self):
  e=self.entries[0];self.assertEqual(bayley.validate_claims({'claims':[{'evidence_id':e['id'],'quote':e['text']}]},self.entries),[e])
 def test_semantic_fallback(self):
  with patch.dict(os.environ,{'BAYLEY_WEBUI_API_KEY':'test'}),patch('bayley.document_vectors',side_effect=TimeoutError):
   results,_,mode,error=bayley.retrieve('canvas',self.entries,{},True)
   self.assertEqual(results[0]['id'],'it');self.assertEqual(mode,'Keyword fallback')
 def test_semantic_only_match(self):
  with patch.dict(os.environ,{'BAYLEY_WEBUI_API_KEY':'test'}),patch('bayley.document_vectors',return_value=[[1,0]]),patch('bayley.embed',return_value=[[1,0]]):
   results,_,mode,_=bayley.retrieve('institutional chief',[self.entries[0]],{},True)
   self.assertEqual(results[0]['id'],'president');self.assertTrue(mode.startswith('Hybrid'))
 def test_draft_is_user_reviewable(self):
  e=next(x for x in self.entries if x['id']=='it');s,b=draft('Canvas login fails',e)
  self.assertIn('Canvas login fails',b);self.assertIn('[fill in]',b);self.assertTrue(mailto(e['contact_email'],s,b).startswith('mailto:AskIT@sfbu.edu?'))
 def test_all_sources_resolve(self):
  for e in self.entries:
   self.assertTrue(e['source_owner']);self.assertTrue(e['checked_on'])
   for sid in e['source_ids']:self.assertIn(sid,self.sources)

if __name__=='__main__':unittest.main()
