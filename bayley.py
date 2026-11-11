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

def completion(messages):
    result=api('/api/chat/completions',{'model':os.environ.get('BAYLEY_MODEL','qwen3:8b'),
        'messages':messages,'temperature':0,'stream':False,'max_tokens':1800})
    choice=result['choices'][0]
    if choice.get('finish_reason')=='length': raise ValueError('Truncated answer')
    content=choice['message'].get('content')
    if not isinstance(content,str) or not content.strip(): raise ValueError('Empty answer')
    content=re.sub(r'<think>.*?</think>','',content,flags=re.S).strip()
    if content.startswith('```'): content=re.sub(r'^```(?:json)?\s*|\s*```$','',content)
    value=json.loads(content)
    if not isinstance(value,dict): raise ValueError('Expected JSON object')
    return value


def bounded_history(history):
    # Previous assistant text is conversation context, not a source of policy facts.
    return [{'role':m['role'],'text':m.get('text','')[:1200]}
        for m in (history or [])[-6:] if m.get('role') in ('user','assistant')]


def validate_answer(result,entries):
    paragraphs=result.get('paragraphs')
    if not isinstance(paragraphs,list) or len(paragraphs)>4: raise ValueError('Invalid paragraphs')
    by_id={e['id']:e for e in entries}; used=[]; output=[]
    for item in paragraphs:
        text=item.get('text'); refs=item.get('evidence',[])
        if not isinstance(text,str) or not text.strip() or len(text)>1200 or not refs: raise ValueError('Missing text or evidence')
        cited=[]
        for ref in refs:
            e=by_id.get(ref.get('id')); quote=ref.get('quote','')
            if not e or not isinstance(quote,str) or len(quote.strip())<10 or quote not in e['text']: raise ValueError('Invalid citation')
            if e not in cited: cited.append(e)
            if e not in used: used.append(e)
        support=' '.join(e['text'] for e in cited).casefold()
        # Reject changed numbers, invented email addresses and all model-authored links.
        for number in re.findall(r'\b\d+\b',text):
            if number not in re.findall(r'\b\d+\b',support): raise ValueError('Unsupported number')
        for email in re.findall(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]+',text):
            if email.casefold() not in support: raise ValueError('Unsupported contact')
        if re.search(r'https?://|www\.|\]\(',text,re.I): raise ValueError('Use application source links')
        output.append({'text':text.strip(),'evidence_ids':[e['id'] for e in cited]})
    return {'paragraphs':output,'entries':used}


def draft_answer(question,entries,history=None):
    data={'question':question,'conversation_context':bounded_history(history),
        'evidence':[{'id':e['id'],'text':e['text'],'term':e.get('term'),'program':e['program']} for e in entries]}
    result=completion([{'role':'system','content':(ROOT/'prompts/guide.txt').read_text()},
        {'role':'user','content':json.dumps(data)+'\n/no_think'}])
    return validate_answer(result,entries)


IDENTITY = "Hi! I’m Bayley, your SFBU student guide. I can help you find school information, understand published deadlines, and prepare a request for the right office. I’m a student-built AI prototype, and I’ll tell you when I don’t have enough information. What can I help you with?"


def conversational_kind(question):
    q=question.lower().strip(' .!?')
    q=re.sub(r'^(hi|hello|hey)[,! ]+','',q)
    if q in ['hi','hello','hey','who are you','what are you','what can you do','introduce yourself','what is your name',"what’s your name","what's your name"]: return 'identity'
    if q in ['thanks','thank you','thank you bayley']: return 'thanks'
    # Narrow general-help scope; school-specific information still requires evidence.
    if not re.search(r'\b(sfbu|policy|deadline|calendar|professor|tuition|visa|cpt|opt)\b',q) and re.search(r'study (plan|tips|better)|manage my time|time management|procrastinat|prepare for (an? )?exam',q): return 'general'
    return 'school'


def general_reply(question,history):
    result=completion([{'role':'system','content':
        'You are Bayley, a warm SFBU student-guide prototype. Give brief general study/time-management suggestions. '
        'Do not claim school-specific policies, dates, staff, services, or actions. Do not invent personal circumstances. '
        'Label the advice as general, not SFBU policy. Ask a focused question if needed. '
        'Return only JSON {"answer":"your response"}. No links, contact addresses or claims that you sent or scheduled anything.'},
        {'role':'user','content':json.dumps({'question':question,'context':bounded_history(history)})+'\n/no_think'}])
    text=result.get('answer')
    if not isinstance(text,str) or not text.strip() or len(text)>2200 or re.search(r'https?://|[\w.+-]+@[\w.-]+',text): raise ValueError('Invalid general answer')
    return text.strip()


def no_evidence_reply(question,history):
    result=completion([{'role':'system','content':
        'You are Bayley. No verified evidence was found for the student question. '
        'Ask ONE short clarifying question that helps identify the topic, service or program. '
        'Do not answer the factual question, suggest facts, name departments, or invent dates/contacts. '
        'Return only JSON {"clarification":"one question?"}. Maximum 220 characters.'},
        {'role':'user','content':json.dumps({'question':question,'context':bounded_history(history)})+'\n/no_think'}])
    text=result.get('clarification','')
    if not isinstance(text,str) or not text.endswith('?') or len(text)>220 or text.count('?')!=1 or re.search(r'\d|https?://|@|\n',text): raise ValueError('Invalid clarification')
    return 'I don’t have verified SFBU information for that yet. '+text


def answer_question(question,entries,context,semantic=True,history=None):
    kind=conversational_kind(question)
    ctx=dict(context)
    response={'role':'assistant','question':question,'entries':[],'context':ctx,'paragraphs':[],
        'mode':'Configured identity','text':'','status':'conversation'}
    if kind=='identity': response['text']=IDENTITY; return response
    if kind=='thanks': response['text']='You’re welcome! What else can I help you find?'; return response
    if kind=='general':
        response.update(text='General study guidance: choose one manageable task, set a short focused work session, and review what you learned. What subject are you working on?',mode='General guidance · built-in fallback')
        if os.environ.get('BAYLEY_WEBUI_API_KEY'):
            try:
                response['text']=general_reply(question,history);response['mode']='General guidance · '+os.environ.get('BAYLEY_MODEL','qwen3:8b')
            except Exception as exc:response['diagnostic']=type(exc).__name__
        return response
    # Reuse the prior user topic only for explicit short follow-ups. Do not infer new facts.
    followup=bool(re.search(r'\b(them|their|that|it|same)\b',question.lower()) or re.search(r'^(and |what about|how about)',question.lower()))
    explicit=any(re.search(r'\b'+re.escape(k)+r'\b',question.lower()) for e in entries for k in e['keywords'] if len(k)>3)
    query_input=question
    if followup and not explicit and ctx.get('last_question'):
        query_input=ctx['last_question']+' Follow-up: '+question
    query,ctx,clarify=resolve_context(query_input,ctx)
    response['context']=ctx
    if clarify:response.update(text=clarify,mode='Clarification');return response
    matches,clashes,mode,warning=retrieve(query,entries,ctx,semantic)
    response.update(mode=mode,diagnostic=warning)
    if clashes:
        response.update(text='The available sources disagree on this point. Please confirm with the responsible office before relying on either version.',entries=clashes,status='conflict'); return response
    if not matches:
        response.update(text='I don’t have verified SFBU information for that question yet. Could you clarify the service or topic you need help with?',status='missing')
        if os.environ.get('BAYLEY_WEBUI_API_KEY'):
            try:response['text']=no_evidence_reply(question,history);response['mode']+=' · model clarification'
            except Exception as exc:response['diagnostic']=type(exc).__name__
        return response
    response.update(text='Here’s what I found in the SFBU sources:',entries=matches,status='answered')
    if os.environ.get('BAYLEY_WEBUI_API_KEY'):
        try:
            generated=draft_answer(query,matches,history)
            if not generated['paragraphs']:
                response.update(text='The retrieved notes don’t answer that question clearly. Could you tell me more about what you need?',entries=[],status='missing')
            else:
                response.update(text='\n\n'.join(p['text'] for p in generated['paragraphs']),paragraphs=generated['paragraphs'],entries=generated['entries'])
            response['mode']+=' · '+os.environ.get('BAYLEY_MODEL','qwen3:8b')
        except Exception as exc:
            response['mode']+=' · source-note fallback';response['diagnostic']=type(exc).__name__
    if response['status']=='answered':ctx['last_question']=query_input[-1500:]
    return response
