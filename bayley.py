"""Evidence retrieval, conversation context and local-model clients."""
import hashlib
import json
import math
import os
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).parent
STOP = set('the a an is are of in on at to for i my me do does can how what when where who sfbu university school please and it this that'.split())

def load_data():
    return (json.loads((ROOT/'data/sources.json').read_text()), json.loads((ROOT/'data/entries.json').read_text()))

def tokens(s):
    s = s.lower().replace('presendate','president').replace('presidant','president')
    return [t for t in re.findall(r'[a-z0-9]+',s) if t not in STOP]

def api(path,payload):
    url=os.environ.get('BAYLEY_WEBUI_URL','http://localhost:8080').rstrip('/')+path
    req=Request(url,data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+os.environ['BAYLEY_WEBUI_API_KEY'],'Content-Type':'application/json'})
    with urlopen(req,timeout=90) as r: return json.load(r)

def embed(texts):
    result=api('/ollama/api/embed',{'model':'nomic-embed-text:v1.5','input':texts})['embeddings']
    if len(result)!=len(texts) or not result or not result[0]: raise ValueError('Invalid embedding response')
    dim=len(result[0])
    if any(len(v)!=dim or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in v) or sum(x*x for x in v)==0 for v in result): raise ValueError('Invalid vectors')
    return result

def document_text(e): return e['title']+' '+e['text']+' '+' '.join(e['keywords'])

def document_vectors(entries):
    # Cache public document vectors only. Questions and API keys are never cached.
    texts=[document_text(e) for e in entries]
    fingerprint=hashlib.sha256(json.dumps([os.environ.get('BAYLEY_WEBUI_URL','http://localhost:8080'),'nomic-embed-text:v1.5',texts]).encode()).hexdigest()
    directory=ROOT/'.cache'; path=directory/(fingerprint+'.json')
    if path.exists(): return json.loads(path.read_text())
    vectors=[]
    for start in range(0,len(texts),16): vectors.extend(embed(['search_document: '+t for t in texts[start:start+16]]))
    directory.mkdir(exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(vectors)); temporary.replace(path)
    return vectors

def cosine(a,b):
    if len(a)!=len(b): raise ValueError('Vector dimension mismatch')
    return sum(x*y for x,y in zip(a,b))/math.sqrt(sum(x*x for x in a)*sum(x*x for x in b))

def lexical_scores(question,entries):
    docs=[tokens(document_text(e)) for e in entries]; query=tokens(question)
    avg=sum(map(len,docs))/max(len(docs),1)
    scores=[]
    for doc in docs:
        counts=Counter(doc); score=0.0
        for word in set(query):
            n=sum(word in d for d in docs); f=counts[word]
            idf=math.log(1+(len(docs)-n+0.5)/(n+0.5))
            score+=idf*f*2.5/(f+1.5*(.25+.75*len(doc)/max(avg,1)))
        scores.append(score)
    return scores

def resolve_context(question,context):
    ctx=dict(context); q=question.lower()
    seasons=re.findall(r'\b(spring|summer|fall|winter)\b',q); years=re.findall(r'\b20\d{2}\b',q)
    if len(set(seasons))>1 or len(set(years))>1: return question,ctx,'Please ask about one term and year at a time.'
    if seasons:
        if ctx.get('season')!=seasons[0] and not years: ctx.pop('year',None)
        ctx['season']=seasons[0]
    if years: ctx['year']=years[0]
    if re.search(r'\bpro\s*\+|\b8[- ]week',q): ctx['program']='Pro+'
    elif 'standard' in q: ctx['program']='standard semester'
    date_words=r'\b(start|starts|begin|begins|drop|add|withdraw|withdrawal|deadline|exams?|finals?|end|ends|registration)\b'
    calendar=bool(re.search(date_words,q))
    # A bare term/year answers a pending clarification, retaining its question.
    if ctx.get('pending_question') and (seasons or years or 'standard' in q or 'pro+' in q):
        question=ctx['pending_question']+' '+question; calendar=True
    if calendar:
        if not ctx.get('season') or not ctx.get('year'):
            ctx['pending_question']=question
            return question,ctx,'Which term and year do you mean—for example, Spring 2027?'
        if not ctx.get('program'):
            ctx['pending_question']=question
            return question,ctx,'Is this for a standard semester or a Pro+ program?'
        ctx.pop('pending_question',None)
        question += ' '+ctx['season']+' '+ctx['year']
    return question,ctx,None

def conflicts(entries):
    groups={}
    for e in entries:
        key=(e.get('fact_key'),e.get('term'),e.get('program'))
        groups.setdefault(key,[]).append(e)
    return [e for group in groups.values() if len({x.get('fact_value',x['text']) for x in group})>1 for e in group]

def retrieve(question,entries,context,semantic=True,today=None):
    today=today or date.today().isoformat()
    calendar=bool(re.search(r'\b(start|starts|begin|begins|drop|add|withdraw|withdrawal|deadline|exams?|finals?|end|ends|registration)\b',question.lower()))
    term=(context.get('season','')+' '+context.get('year','')).strip().title()
    candidates=[]
    for e in entries:
        if calendar and e.get('topic')=='calendar':
            if e.get('term')!=term or context.get('program')!='standard semester': continue
        elif e.get('topic')=='calendar': continue
        # Calendar entries are intentionally selectable for their requested future term.
        if e.get('topic')!='calendar' and ((e.get('effective_from') and today<e['effective_from']) or (e.get('effective_to') and today>e['effective_to'])): continue
        if not e.get('checked_on'): continue
        candidates.append(e)
    scores=lexical_scores(question,candidates); semantic_scores=[0.0]*len(candidates)
    mode='Keyword retrieval'; warning=None
    if semantic and candidates and os.environ.get('BAYLEY_WEBUI_API_KEY'):
        try:
            vectors=document_vectors(candidates); query=embed(['search_query: '+question])[0]
            semantic_scores=[cosine(query,v) for v in vectors]; mode='Hybrid retrieval · BM25 + Nomic'
        except Exception as exc:
            mode='Keyword fallback'; warning=type(exc).__name__
    # Conservative candidate gate; similarity is not a probability of correctness.
    best=max(scores,default=0)
    eligible=[i for i in range(len(candidates)) if (scores[i]>0 and scores[i]>=best*.6) or (semantic_scores[i]>=.65 and scores[i]==0)]
    lex_order=sorted(eligible,key=lambda i:scores[i],reverse=True)
    sem_order=sorted(eligible,key=lambda i:semantic_scores[i],reverse=True)
    rank=lambda i:1/(60+lex_order.index(i))+ (1/(60+sem_order.index(i)) if mode.startswith('Hybrid') else 0)
    chosen=sorted(eligible,key=rank,reverse=True)[:3]
    matches=[candidates[i] for i in chosen]
    # Include competing versions even if ranking puts one outside the top three.
    keys={(e['fact_key'],e.get('term'),e['program']) for e in matches}
    competing=[e for e in candidates if (e['fact_key'],e.get('term'),e['program']) in keys]
    return matches,conflicts(competing),mode,warning

def validate_claims(result,entries):
    by_id={e['id']:e for e in entries}; claims=result.get('claims')
    if not isinstance(claims,list) or len(claims)>3: raise ValueError('Invalid claims')
    validated=[]
    for c in claims:
        e=by_id.get(c.get('evidence_id')); quote=c.get('quote','')
        if not e or not isinstance(quote,str) or len(quote.strip())<10 or quote not in e['text']: raise ValueError('Unsupported evidence')
        # Display the complete verified note, preserving conditions around excerpts.
        if e not in validated: validated.append(e)
    return validated

def draft_answer(question,entries):
    result=api('/api/chat/completions',{'model':os.environ.get('BAYLEY_MODEL','qwen3:8b'),'messages':[{'role':'system','content':(ROOT/'prompts/guide.txt').read_text()},{'role':'user','content':json.dumps({'question':question,'evidence':[{'id':e['id'],'text':e['text'],'term':e.get('term'),'program':e['program']} for e in entries]})+'\n/no_think'}],'temperature':0,'stream':False,'max_tokens':1400})
    choice=result['choices'][0]
    if choice.get('finish_reason')=='length': raise ValueError('Truncated answer')
    content=choice['message']['content'].strip()
    if content.startswith('```'): content=re.sub(r'^```(?:json)?\s*|\s*```$','',content)
    return validate_claims(json.loads(content),entries)

def answer_question(question,entries,context,semantic=True):
    query,ctx,clarify=resolve_context(question,context)
    response={'role':'assistant','question':question,'entries':[],'context':ctx,'mode':'Clarification','text':clarify or ''}
    if clarify: return response
    matches,clashes,mode,warning=retrieve(query,entries,ctx,semantic)
    response.update(mode=mode,diagnostic=warning)
    if clashes:
        response.update(text='I found conflicting source notes for the same topic and scope. Please confirm with the responsible office before relying on either.',entries=clashes,status='conflict'); return response
    if not matches:
        response.update(text='I don’t have verified evidence for that question yet. The SFBU contact directory can help you find the right office.',status='missing'); return response
    selected=matches
    if os.environ.get('BAYLEY_WEBUI_API_KEY'):
        try:
            selected=draft_answer(query,matches); response['mode']+=' · '+os.environ.get('BAYLEY_MODEL','qwen3:8b')
        except Exception as exc:
            response['mode']+=' · source-note fallback'; response['diagnostic']=type(exc).__name__
    if not selected:
        response.update(text='The retrieved notes do not answer that question clearly. Please check with the relevant office.',status='missing'); return response
    response.update(text='Here’s what the available SFBU sources say:',entries=selected,status='answered')
    return response
