"""Minimal search-to-chat interface for Ask Bayley."""
import base64
import os
from pathlib import Path
from urllib.error import URLError

import streamlit as st
from bayley import draft_answer, find_entries, load_data

MASCOT = Path(__file__).parent / 'assets' / 'bayley.png'
st.set_page_config(page_title='Ask Bayley · SFBU', page_icon=str(MASCOT), layout='centered', initial_sidebar_state='collapsed')
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
[data-testid="stChatMessageAvatarCustom"] { object-fit:contain; background:white; border-radius:50%; }
@keyframes arrive { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
@media (prefers-reduced-motion: reduce) { * { animation:none !important; } }
</style>''', unsafe_allow_html=True)

sources, entries = load_data()
live = bool(os.environ.get('BAYLEY_WEBUI_API_KEY'))
if 'messages' not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader('Ask Bayley')
    st.caption('SFBU student guide · Hackathon prototype')
    st.caption(f"Model: {os.environ.get('BAYLEY_MODEL', 'qwen3:32b')} · API key configured" if live else 'Source-note preview · No model connected')
    st.caption('A configured key is not proof of a successful API request. Each reply shows its mode.')
    if st.button('New conversation'):
        st.session_state.messages = []
        st.rerun()
    st.subheader('SFBU sources')
    for source in sources.values():
        st.markdown(f"[{source['title']}]({source['url']})")
    st.caption('Limited curated notes. Calendar coverage: Spring and Summer 2027 standard semesters. Verify important decisions with SFBU.')


def render_reply(message):
    with st.chat_message('assistant', avatar=str(MASCOT)):
        st.markdown(message['text'])
        st.caption(message['mode'])
        if message.get('entries'):
            with st.expander('Sources and supporting notes'):
                for entry in message['entries']:
                    st.markdown(f"**{entry['title']}**")
                    st.write(entry['text'])
                    st.caption(entry['section'])
                    st.markdown(' · '.join(f"[{sources[s]['title']}]({sources[s]['url']})" for s in entry['source_ids']))


has_chat = bool(st.session_state.messages)
if not has_chat:
    st.markdown('<div class="bayley-home"><h1>Ask Bayley</h1><p>Your SFBU student guide.</p></div>', unsafe_allow_html=True)
    # A container keeps the initial input inline, above the mascot.
    with st.container():
        question = st.chat_input('What would you like to know about SFBU?', key='home_question', max_chars=1000)
    encoded = base64.b64encode(MASCOT.read_bytes()).decode('ascii')
    st.markdown(f'<div class="bayley-mascot"><img src="data:image/png;base64,{encoded}" alt="Bayley the Bayhawk, SFBU mascot"></div>', unsafe_allow_html=True)
    st.markdown('<div class="bayley-footnote">Deadlines, policies, and campus support.<br>Student-built prototype · Answers grounded in available SFBU notes.</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="bayley-chat-title">Ask Bayley</div>', unsafe_allow_html=True)
    st.caption('Your SFBU student guide')
    for message in st.session_state.messages:
        if message['role'] == 'user':
            with st.chat_message('user'):
                st.write(message['text'])
        else:
            render_reply(message)
    question = st.chat_input('Message Bayley…', key='chat_question', max_chars=1000)

if question and question.strip():
    st.session_state.messages.append({'role': 'user', 'text': question.strip()})
    st.session_state.pending = question.strip()
    st.rerun()

# Rerun first so the mascot changes to an avatar before a slow model request.
if st.session_state.get('pending'):
    question = st.session_state.pop('pending')
    matches, needs_term = find_entries(question, entries)
    mode = 'Source-note preview · No model used'
    if needs_term:
        answer = 'Which term and year do you mean? Please include them in your question—for example, “When do classes start in Spring 2027?”'
    elif not matches:
        answer = "I couldn’t find that in my available SFBU notes. You can check the official links in the sidebar. I won’t guess a date or policy."
    else:
        answer = '\n\n'.join(entry['text'] for entry in matches)
        if live:
            with st.spinner('Bayley is checking the source notes…'):
                try:
                    answer = draft_answer(question, matches)
                    mode = f"Model reply · {os.environ.get('BAYLEY_MODEL', 'qwen3:32b')}"
                except (URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError):
                    mode = 'Model unavailable · Showing source notes'
    st.session_state.messages.append({'role': 'assistant', 'text': answer, 'entries': matches, 'mode': mode})
    st.rerun()
