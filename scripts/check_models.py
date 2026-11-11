"""Run from the project root: .venv/bin/python scripts/check_models.py"""
import os
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from bayley import embed,load_data,document_vectors,draft_answer
if not os.environ.get('BAYLEY_WEBUI_API_KEY'):
    sys.exit('Set BAYLEY_WEBUI_API_KEY in this terminal first. Do not paste it into source files.')
_,entries=load_data()
def check_answer():
    evidence=next(e for e in entries if e['id']=='president')
    result=draft_answer('Who is SFBU president?',[evidence])
    if not result['paragraphs']: raise ValueError('Model returned no answer')
    return 'cited paragraphs: '+str(len(result['paragraphs']))
failed=False
for name,operation in [('Nomic embedding',lambda: len(embed(['search_query: Canvas login help'])[0])),('Public document index',lambda:len(document_vectors(entries))),('Cited Qwen response',check_answer)]:
    start=time.monotonic()
    try: print(name,'PASS',operation(),f'{time.monotonic()-start:.1f}s')
    except Exception as e:
        failed=True
        print(name,'FAIL',type(e).__name__,'— check WebUI permissions/model and connection settings')
sys.exit(1 if failed else 0)
