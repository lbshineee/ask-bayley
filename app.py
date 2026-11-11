"""Ask Bayley: minimal interface with evidence and reviewable handoffs."""
import base64
import os
from pathlib import Path
import streamlit as st
from bayley import load_data, answer_question
from actions import draft, mailto
ROOT=Path(__file__).parent
MASCOT=ROOT/'assets/bayley.png'
st.set_page_config(page_title='Ask Bayley · SFBU',page_icon=str(MASCOT),layout='centered',initial_sidebar_state='collapsed')
st.markdown('''<style>
.stApp { background: #fff; color: #17364c; }
.block-container { max-width: 800px; padding-top: 2rem; padding-bottom: 3rem; }
header[data-testid="stHeader"] { background: transparent; }
.bayley-home { text-align: center; padding-top: clamp(24px, 10vh, 110px); }
.bayley-home h1 { color: #0c4266; font-size: clamp(40px, 7vw, 60px); letter-spacing: -2px; font-weight: 700; padding-bottom: 6px; }
.bayley-home p { color: #74818a; font-size: 15px; margin-bottom: 28px; }
.bayley-mascot { text-align:center; padding: 30px 0 8px; animation: arrive .35s ease-out; }
.bayley-mascot img { width: 235px; max-width: 52vw; height:auto; }
.bayley-footnote { text-align:center; color:#89939a; font-size:12px; padding: 14px 0; }
.bayley-chat-title { color:#0c4266; font-size:24px; font-weight:650; margin-bottom:2px; }
[data-testid="stChatInput"] { border-radius: 28px; border:1px solid #dce2e6; background:white; box-shadow:0 3px 14px #143a5810; }
[data-testid="stChatMessage"] { background:#f7f9fb; border-radius:18px; animation:arrive .25s ease-out; }
@keyframes arrive { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
@media (prefers-reduced-motion: reduce) { * { animation:none !important; } }
</style>''', unsafe_allow_html=True)

sources, entries = load_data()
encoded=base64.b64encode(MASCOT.read_bytes()).decode('ascii')
# Frame the original PNG with an SVG viewport; the source mascot is unchanged.
portrait=f'<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="680 0 600 600"><rect x="680" width="600" height="600" fill="#edf3f6"/><image href="data:image/png;base64,{encoded}" width="2048" height="1763"/></svg>' 
for key,default in [('messages',[]),('context',{}),('feedback',{})]:
    if key not in st.session_state: st.session_state[key]=default

def reset():
    st.session_state.messages=[]; st.session_state.context={}; st.session_state.feedback={}
    for key in list(st.session_state):
        if key.startswith(('subject_','body_','vote_')): del st.session_state[key]
    st.session_state.pop('pending',None)

def submit(q):
    st.session_state.messages.append({'role':'user','text':q})
    st.session_state.pending=q
    st.rerun()

with st.sidebar:
    st.subheader('Sources')
    for source in sources.values():
        st.markdown(f"[{source['title']}]({source['url']})")
    st.caption('A source link is not proof that the full document is indexed. This version uses 26 reviewed notes.')
    with st.expander('Connection and retrieval'):
        st.caption('Model: '+os.environ.get('BAYLEY_MODEL','qwen3:8b'))
        st.caption('API key configured' if os.environ.get('BAYLEY_WEBUI_API_KEY') else 'No API key · source notes only')
        semantic=st.checkbox('Use semantic retrieval',value=True)
        st.caption('Nomic uses the WebUI Ollama proxy. If unavailable, keyword retrieval continues.')
    st.caption('Student-built prototype. Feedback stays in this browser session; it is not sent to an analytics service.')

# Keep this control visible even with the sidebar closed.
_,control=st.columns([3,2])
with control: st.button('New conversation',on_click=reset,use_container_width=True)

def render_reply(message,index):
    with st.chat_message('assistant',avatar=portrait):
        evidence=message.get('entries',[])
        numbers={e['id']:n for n,e in enumerate(evidence,1)}
        if message.get('paragraphs'):
            by_id={e['id']:e for e in evidence}
            for paragraph in message['paragraphs']:
                links=[]
                for eid in paragraph['evidence_ids']:
                    source=sources[by_id[eid]['source_ids'][0]]
                    links.append(f"[Evidence {numbers[eid]}]({source['url']})")
                st.markdown(paragraph['text']+'  '+ ' · '.join(links))
        else:
            st.markdown(message['text'])
            for n,e in enumerate(evidence,1):
                source=sources[e['source_ids'][0]]
                st.markdown(f"{e['text']} **[Evidence {n}]({source['url']})**")
        if message.get('context',{}).get('season'):
            ctx=message['context']; st.caption('Conversation context: '+ctx.get('season','').title()+' '+ctx.get('year','')+' · '+ctx.get('program','program not specified'))
        if message.get('entries'):
            with st.expander('Evidence and applicability'):
                for n,e in enumerate(message['entries'],1):
                    st.markdown(f"**Evidence {n} · {e['title']}**")
                    st.write(e['text'])
                    st.caption(f"Section: {e['section']} · Owner: {e['source_owner']} · Checked: {e['checked_on']}")
                    st.caption(f"Scope: {e.get('term') or 'No term specified'} · {e['program']} · Effective: {e.get('effective_from') or 'Not stated'} to {e.get('effective_to') or 'Not stated'}")
                    for sid in e['source_ids']: st.markdown(f"[{sources[sid]['title']}]({sources[sid]['url']})")
        if message.get('status') in ['missing','conflict']:
            st.link_button('Find the right SFBU office',sources['contact']['url'])
        contacts=[e for e in message.get('entries',[]) if e.get('contact_email')]
        if contacts and message.get('status')!='conflict':
            with st.expander('Next step · Prepare a request'):
                target=st.selectbox('Department',contacts,format_func=lambda e:e['title'],key=f'target_{index}')
                subject,body=draft(message['question'],target)
                suffix=f"{index}_{target['id']}"
                st.caption('Draft only. Review and edit before sharing. Do not include passwords or API keys.')
                st.text_input('To',value=target['contact_email'],disabled=True,key='to_'+suffix)
                subject=st.text_input('Subject',value=subject,key='subject_'+suffix)
                body=st.text_area('Message',value=body,height=220,key='body_'+suffix)
                st.link_button('Open email draft',mailto(target['contact_email'],subject,body))
                st.download_button('Download draft',subject+'\n\n'+body,file_name='bayley-request.txt',key='download_'+suffix)
                if target['id']=='it': st.link_button('Open official AskIT form',sources['askit']['url'])
                st.caption('Opening your email app does not send the message. Copy the draft into the IT form if using the form.')
        with st.expander('Was this useful?'):
            choice=st.radio('Your feedback',['Not rated','Helpful','Needs improvement'],key=f'vote_{index}',horizontal=True,label_visibility='collapsed')
            st.session_state.feedback[index]=choice
            st.caption('Session-only feedback. No chat transcript is submitted.')
        with st.expander('How this answer was produced'):
            st.caption(message['mode'])
            if message.get('diagnostic'): st.caption('Connection or validation issue: '+message['diagnostic'])

if not st.session_state.messages:
    st.markdown('<div class="bayley-home"><h1>Ask Bayley</h1><p>Your SFBU student guide.</p></div>',unsafe_allow_html=True)
    with st.container(): question=st.chat_input('What would you like to know about SFBU?',key='home_question',max_chars=1000)
    for col,q in zip(st.columns(3),['Who is SFBU’s president?','Where do I get Canvas help?','How do I join a club?']):
        with col:
            if st.button(q,use_container_width=True): submit(q)
    st.markdown(f'<div class="bayley-mascot"><img src="data:image/png;base64,{encoded}" alt="Bayley the Bayhawk"></div>',unsafe_allow_html=True)
    st.markdown('<div class="bayley-footnote">Official sources. Practical next steps.<br>Student-built SFBU guide.</div>',unsafe_allow_html=True)
else:
    st.markdown('<div class="bayley-chat-title">Ask Bayley</div>',unsafe_allow_html=True)
    st.caption('Your SFBU student guide')
    follow_latest=st.checkbox('Follow new replies',value=True,help='Turn off to read earlier messages without automatic scrolling.')
    with st.container(height=480,border=False,key='conversation',autoscroll=follow_latest):
        for i,message in enumerate(st.session_state.messages):
            if message['role']=='user':
                with st.chat_message('user'): st.write(message['text'])
            else: render_reply(message,i)
    question=st.chat_input('Message Bayley…',key='chat_question',max_chars=1000)
if question and question.strip(): submit(question.strip())
if st.session_state.get('pending'):
    q=st.session_state.pop('pending')
    with st.spinner('Checking the available SFBU evidence…'):
        reply=answer_question(q,entries,st.session_state.context,semantic,history=st.session_state.messages[:-1])
    st.session_state.context=reply['context']
    st.session_state.messages.append(reply)
    st.rerun()
