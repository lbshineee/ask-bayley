"""Run synthetic Ask Bayley scenarios sequentially; never declare answer accuracy.

Offline mode disables network/model access. Live mode uses the configured local
WebUI and writes actual responses for human review. No additional dependencies.
"""
import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import getpass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time
from unittest.mock import patch
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bayley
from actions import draft


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def visible_answer(reply, sources):
    parts = [reply.get('text', '')]
    if not reply.get('paragraphs'):
        parts.extend(e['text'] for e in reply.get('entries', []))
    if reply.get('status') == 'draft':
        for e in reply.get('entries', []):
            if e.get('contact_email'):
                subject, body = draft(reply['draft_question'], e)
                parts.append(f"Editable draft to {e['contact_email']}\nSubject: {subject}\n{body}")
    urls = sorted({sources[s]['url'] for e in reply.get('entries', [])
                   for s in e.get('source_ids', []) if s in sources})
    return '\n\n'.join(filter(None, parts)), urls


def check_expectations(reply, expect, api_calls, rendered):
    """Limited observable checks. These cannot judge semantic truth/usefulness."""
    errors = []
    ids = [e['id'] for e in reply.get('entries', [])]
    if 'statuses' in expect and reply.get('status') not in expect['statuses']:
        errors.append('status: expected ' + '/'.join(expect['statuses']) + '; got ' + str(reply.get('status')))
    if any(i not in ids for i in expect.get('evidence_all', [])):
        errors.append('required evidence missing: ' + ','.join(expect['evidence_all']))
    if 'evidence_exact' in expect and set(ids) != set(expect['evidence_exact']):
        errors.append('unexpected evidence IDs: ' + ','.join(ids))
    if 'allowed_evidence' in expect and not set(ids).issubset(expect['allowed_evidence']):
        errors.append('irrelevant evidence IDs: ' + ','.join(set(ids)-set(expect['allowed_evidence'])))
    if expect.get('mode_contains', '') not in reply.get('mode', ''):
        errors.append('unexpected response mode: ' + reply.get('mode', ''))
    if expect.get('mode_not_contains') and expect['mode_not_contains'] in reply.get('mode', ''):
        errors.append('unexpected response mode: ' + reply.get('mode', ''))
    for key in expect.get('context_absent', []):
        if key in reply.get('context', {}): errors.append('stale context: ' + key)
    for fragment in expect.get('draft_contains', []):
        if fragment.casefold() not in reply.get('draft_question', '').casefold():
            errors.append('draft lost original detail: ' + fragment)
    for fragment in expect.get('forbid_text', []):
        if fragment.casefold() in rendered.casefold():
            errors.append('requires review of forbidden phrase: ' + fragment)
    if 'api_calls_max' in expect and api_calls > expect['api_calls_max']:
        errors.append('unexpected API request before early response')
    return errors


def latency(values):
    if not values: return None
    values = sorted(values)
    return {'n': len(values), 'median_seconds': round(statistics.median(values), 3),
            'p95_seconds': round(values[max(0, math.ceil(.95*len(values))-1)], 3),
            'max_seconds': round(max(values), 3)}


def load_cases(path, smoke=False, limit=None):
    suite = json.loads(path.read_text())
    cases = suite['cases']
    ids = [c['id'] for c in cases]
    if len(set(ids)) != len(ids): raise ValueError('Duplicate case IDs')
    if smoke: cases = [c for c in cases if c.get('smoke')]
    return cases[:limit] if limit else cases


def preflight(model):
    base = os.environ['BAYLEY_WEBUI_URL'].rstrip('/')
    parsed = urlparse(base)
    if parsed.scheme not in ('http', 'https') or parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Use the local WebUI address on this machine (localhost).')
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('WebUI URL must not contain credentials, query parameters or fragments.')
    req = Request(base+'/api/models', headers={'Authorization': 'Bearer '+os.environ['BAYLEY_WEBUI_API_KEY']})
    with urlopen(req, timeout=15) as response:
        data = json.load(response)
    names = {m.get('id') for m in data.get('data', [])}
    required = {model, 'nomic-embed-text:v1.5'}
    if not required.issubset(names):
        raise ValueError('Required models not visible: '+', '.join(sorted(required-names)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True, choices=['offline', 'live'])
    parser.add_argument('--smoke', action='store_true', help='Run 12 representative cases first.')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--webui-url', help='Local Open WebUI root URL; otherwise use environment/platform default.')
    parser.add_argument('--model', choices=['qwen3:8b', 'qwen3:32b'])
    parser.add_argument('--run-note', default='', help='Optional non-secret hardware/load note.')
    parser.add_argument('--output', type=Path, help='New results directory; existing files are never overwritten.')
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1: parser.error('--limit must be positive')
    suite_path = ROOT/'evaluation/cases.json'
    cases = load_cases(suite_path, args.smoke, args.limit)
    model = args.model or os.environ.get('BAYLEY_MODEL', 'qwen3:8b')
    if model not in ('qwen3:8b', 'qwen3:32b'): parser.error('Use an allowed Qwen model.')
    if args.mode == 'live':
        os.environ['BAYLEY_MODEL'] = model
        os.environ['BAYLEY_WEBUI_URL'] = args.webui_url or os.environ.get('BAYLEY_WEBUI_URL') or ('http://localhost:3000' if sys.platform=='darwin' else 'http://localhost:8080')
        if not os.environ.get('BAYLEY_WEBUI_API_KEY'):
            if not sys.stdin.isatty(): parser.error('Run interactively to enter the WebUI API key, or export it in this shell.')
            os.environ['BAYLEY_WEBUI_API_KEY'] = getpass.getpass('Local WebUI API key (hidden): ').strip()
        if not os.environ['BAYLEY_WEBUI_API_KEY']: parser.error('The API key is empty.')
        try: preflight(model)
        except Exception as exc:
            print('Preflight failed:', type(exc).__name__, file=sys.stderr)
            if isinstance(exc, ValueError): print(str(exc), file=sys.stderr)
            print('Check the WebUI URL, API key and model visibility. No evaluation requests were sent.', file=sys.stderr)
            return 2
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    output = args.output or ROOT/'evaluation/results'/f'{timestamp}-{args.mode}'
    output.mkdir(parents=True, exist_ok=False)
    (ROOT/'evaluation/results').mkdir(parents=True, exist_ok=True)
    (ROOT/'evaluation/results/.gitignore').write_text('*\n!.gitignore\n')
    sources, entries = bayley.load_data()
    baseline = json.loads((ROOT/'evaluation/baseline_sha256.json').read_text())
    code_hashes = {name:file_sha(ROOT/name) for name in baseline}
    changed = [name for name in baseline if baseline[name] != code_hashes[name]]
    metadata = {'mode':args.mode,'model':model,'webui_url':os.environ.get('BAYLEY_WEBUI_URL') if args.mode=='live' else None,
                'host':platform.node(),'architecture':platform.machine(),'python':platform.python_version(),
                'started_utc':timestamp,'source_note_count':len(entries),'cases_selected':len(cases),
                'suite_sha256':file_sha(suite_path),'code_sha256':code_hashes,'baseline_differences':changed,
                'existing_cache_files':len(list((ROOT/'.cache').glob('*.json'))),'run_note':args.run_note,
                'claim_boundary':'Backend checks only. Human review is required for answer correctness, citation support and usefulness. No browser rendering test.'}
    (output/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    original_api = bayley.api
    calls = []
    def tracked_api(path, payload):
        record = {'kind':'generation' if path=='/api/chat/completions' else 'embedding','success':False}
        calls.append(record)
        start = time.perf_counter()
        try:
            value = original_api(path,payload)
            record['success'] = True
            return value
        finally: record['seconds'] = time.perf_counter()-start
    rows=[]; interrupted=False
    fields=['case_id','category','scenario','turn','question','expected_behavior','answer','source_urls',
            'status','mode','automatic_checks_passed','automatic_issues','backend_seconds','model_calls','embedding_calls',
            'human_verdict','citation_support','usefulness','reviewer_notes']
    print(f'{args.mode.upper()}: {len(cases)} cases, sequential. Results: {output}',flush=True)
    if changed: print('Code differs from supplied baseline:', ', '.join(changed),flush=True)
    with ExitStack() as stack:
        if args.mode=='offline':
            stack.enter_context(patch.dict(os.environ,{'BAYLEY_WEBUI_API_KEY':''}))
            stack.enter_context(patch.object(bayley,'api',side_effect=RuntimeError('Offline evaluation forbids network access')))
        else: stack.enter_context(patch.object(bayley,'api',side_effect=tracked_api))
        with (output/'results.jsonl').open('w') as raw, (output/'review.csv').open('w',newline='') as cf:
            writer=csv.DictWriter(cf,fieldnames=fields);writer.writeheader()
            try:
                for index, case in enumerate(cases,1):
                    context={};history=[]
                    for turn_no, turn in enumerate(case['turns'],1):
                        before=len(calls); start=time.perf_counter();error=None
                        try:
                            reply=bayley.answer_question(turn['question'],entries,context,
                                                        semantic=args.mode=='live',history=history)
                            rendered,urls=visible_answer(reply,sources)
                        except Exception as exc:
                            error=type(exc).__name__
                            reply={'status':'error','mode':'Runtime error','context':context,'entries':[]}
                            rendered='Runtime error: '+error;urls=[]
                        elapsed=time.perf_counter()-start
                        current=calls[before:]
                        issues=check_expectations(reply,turn['expect'],len(current),rendered)
                        if error: issues.append(error)
                        row={'case_id':case['id'],'category':case['category'],'scenario':case['name'],'turn':turn_no,
                             'question':turn['question'],'expected_behavior':turn['expected_behavior'],'answer':rendered,
                             'source_urls':urls,'status':reply.get('status'),'mode':reply.get('mode'),
                             'automatic_checks_passed':not issues,'automatic_issues':issues,'backend_seconds':round(elapsed,6),
                             'model_calls':sum(x['kind']=='generation' for x in current),
                             'embedding_calls':sum(x['kind']=='embedding' for x in current),
                             'successful_model_calls':sum(x['kind']=='generation' and x['success'] for x in current),
                             'evidence_ids':[e['id'] for e in reply.get('entries',[])],
                             'context':reply.get('context',{}),'human_verdict':'PENDING',
                             'citation_support':'PENDING','usefulness':'PENDING','reviewer_notes':''}
                        raw.write(json.dumps(row,ensure_ascii=False)+'\n');raw.flush()
                        writer.writerow({k:json.dumps(row[k],ensure_ascii=False) if isinstance(row[k],(list,dict)) else row[k] for k in fields});cf.flush()
                        rows.append(row)
                        context=reply.get('context',{})
                        history.extend([{'role':'user','text':turn['question']},{'role':'assistant','text':rendered}])
                    print(f"[{index}/{len(cases)}] {case['id']} {case['category']}: "+('checks passed; human review pending' if all(r['automatic_checks_passed'] for r in rows if r['case_id']==case['id']) else 'CHECK / REVIEW REQUIRED'),flush=True)
            except KeyboardInterrupt:
                interrupted=True
                print('\nStopped. Partial results saved; no retries queued.',flush=True)
    grouped=defaultdict(list)
    for r in rows:grouped[r['case_id']].append(r)
    complete={c['id'] for c in cases if len(grouped[c['id']])==len(c['turns'])}
    passed=[key for key in complete if all(r['automatic_checks_passed'] for r in grouped[key])]
    category_stats={}
    for c in cases:
        if c['id'] not in complete:continue
        stat=category_stats.setdefault(c['category'],{'cases_completed':0,'automatic_checks_passed':0})
        stat['cases_completed']+=1;stat['automatic_checks_passed']+=c['id'] in passed
    summary={'mode':args.mode,'interrupted':interrupted,'cases_completed':len(complete),'prompts_completed':len(rows),
             'cases_passing_automatic_checks':len(passed),'cases_needing_review':len(complete)-len(passed),
             'human_reviewed_cases':0,'answer_accuracy':None,'usefulness_rate':None,
             'model_requests':sum(r['model_calls'] for r in rows),'embedding_requests':sum(r['embedding_calls'] for r in rows),
             'source_note_fallback_turns':sum('fallback' in r['mode'].lower() for r in rows),
             'by_category':category_stats,'latency_by_path':None,
             'claim_boundary':'Passing automatic checks does not establish a correct or useful answer. Offline timings are not LLM/DGX performance measurements.'}
    if args.mode=='live':
        summary['latency_by_path']={
            'turns_with_generation_request':latency([r['backend_seconds'] for r in rows if r['model_calls']]),
            'turns_with_embedding_only':latency([r['backend_seconds'] for r in rows if r['embedding_calls'] and not r['model_calls']]),
            'turns_without_model_api_request':latency([r['backend_seconds'] for r in rows if not r['model_calls'] and not r['embedding_calls']])}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
    print('Review review.csv before making correctness/usefulness claims. Raw responses remain in results.jsonl.',flush=True)
    return 130 if interrupted else (1 if len(passed)<len(complete) else 0)


if __name__=='__main__':
    raise SystemExit(main())
