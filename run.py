"""Launch with this project's Python: .venv/bin/python run.py [--preview]."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview',action='store_true',help='Run source-note preview without model requests')
    args=parser.parse_args()
    os.chdir(ROOT)
    if args.preview:
        os.environ.pop('BAYLEY_WEBUI_API_KEY',None)
        print('Preview mode: no model requests.')
    else:
        default='http://localhost:3000' if sys.platform=='darwin' else 'http://localhost:8080'
        base=os.environ.get('BAYLEY_WEBUI_URL')
        if not base:
            base=input(f'Open WebUI address [{default}]: ').strip() or default
        os.environ['BAYLEY_WEBUI_URL']=base.rstrip('/')
        os.environ.setdefault('BAYLEY_MODEL','qwen3:8b')
        key=os.environ.get('BAYLEY_WEBUI_API_KEY') or getpass.getpass('Open WebUI API key (hidden): ').strip()
        if not key: sys.exit('No key entered. Use --preview for source notes only.')
        os.environ['BAYLEY_WEBUI_API_KEY']=key
        request=Request(base.rstrip('/')+'/api/models',headers={'Authorization':'Bearer '+key})
        try:
            with urlopen(request,timeout=15) as response: data=json.load(response)
            ids={m['id'] for m in data.get('data',[]) if isinstance(m,dict) and 'id' in m}
            if os.environ['BAYLEY_MODEL'] not in ids:
                sys.exit('Selected chat model is not listed by WebUI. Check BAYLEY_MODEL and model permissions.')
            print('WebUI authentication passed; chat model is listed. Generation is checked on each reply.')
            if 'nomic-embed-text:v1.5' not in ids:
                print('Nomic is not listed: semantic retrieval may fall back to keywords.')
        except HTTPError as exc: sys.exit(f'WebUI returned HTTP {exc.code}. Check address, API key and permissions.')
        except Exception as exc: sys.exit(f'WebUI check failed ({type(exc).__name__}). Check that WebUI is running.')
    return subprocess.call([sys.executable,'-m','streamlit','run',str(ROOT/'app.py')])

if __name__=='__main__': sys.exit(main())
