"""Rehearse the six demo messages; optionally exercise the actual local models."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bayley
from actions import draft

QUESTIONS = [
    'Sorry I missed orientation. Anything I should know?',
    'When do classes start?',
    'Spring 2027.',
    'Standard semester.',
    'Canvas says access denied.',
    'Please draft an email to them.',
]


def visible(reply):
    text = reply.get('text', '')
    if not reply.get('paragraphs'):
        text += '\n\n' + '\n\n'.join(e['text'] for e in reply.get('entries', []))
    if reply.get('closing'):
        text += '\n\n' + reply['closing']
    if reply.get('status') == 'draft':
        for entry in reply['entries']:
            subject, body = draft(reply['draft_question'], entry)
            text += '\n\nTo: ' + entry['contact_email'] + '\nSubject: ' + subject + '\n' + body
    return text.strip()


def verify(turn, reply):
    ids = [e['id'] for e in reply.get('entries', [])]
    text = visible(reply)
    if turn == 0:
        assert reply['status'] == 'onboarding', 'Starter guide was not selected'
        assert 'Bayley the Bayhawk' in text and '94539' in text
        assert 'guide-tasks' in ids and 'guide-it' in ids
    elif turn == 1:
        assert reply['status'] == 'clarification' and 'term and year' in text
    elif turn == 2:
        assert reply['status'] == 'clarification' and 'Pro+' in text
    elif turn == 3:
        assert reply['status'] == 'answered' and ids == ['spring-2027-start']
        assert 'January 11, 2027' in text, 'Review the class-start answer'
    elif turn == 4:
        assert reply['status'] == 'answered' and ids == ['it']
        assert 'AskIT@sfbu.edu' in text
        assert not reply.get('show_calendar_context')
    elif turn == 5:
        assert reply['status'] == 'draft' and ids == ['it']
        assert reply['draft_question'] == QUESTIONS[4]
        assert QUESTIONS[4] in text and 'Nothing has been sent' in text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--webui-url', default=os.environ.get('BAYLEY_WEBUI_URL', 'http://localhost:8080'))
    args = parser.parse_args()
    if args.live:
        parsed = urlparse(args.webui_url)
        if parsed.scheme not in ('http', 'https') or parsed.hostname not in ('localhost', '127.0.0.1', '::1') or parsed.username or parsed.password:
            parser.error('Use the local Open WebUI root URL without credentials.')
        os.environ['BAYLEY_WEBUI_URL'] = args.webui_url.rstrip('/')
        os.environ.setdefault('BAYLEY_MODEL', 'qwen3:8b')
        if not os.environ.get('BAYLEY_WEBUI_API_KEY'):
            os.environ['BAYLEY_WEBUI_API_KEY'] = getpass.getpass('Local WebUI API key (hidden): ').strip()
        if not os.environ['BAYLEY_WEBUI_API_KEY']:
            parser.error('API key is empty.')
    else:
        os.environ['BAYLEY_WEBUI_API_KEY'] = ''
    _, entries = bayley.load_data()
    context, history, issues = {}, [], []
    print('LIVE local-model rehearsal' if args.live else 'OFFLINE rehearsal: no model calls')
    for i, question in enumerate(QUESTIONS):
        reply = bayley.answer_question(question, entries, context, semantic=args.live, history=history)
        answer = visible(reply)
        print(f'\n[{i+1}/6] Student: {question}\nBayley: {answer}\nMode: {reply["mode"]}')
        try:
            verify(i, reply)
        except AssertionError as exc:
            issues.append(f'Turn {i+1}: {exc or "unexpected response"}')
        if args.live and i in (3, 4) and ('fallback' in reply['mode'].lower() or reply.get('diagnostic')):
            issues.append(f'Turn {i+1}: inspect model/retrieval fallback before recording')
        context = reply['context']
        history.extend([{'role':'user','text':question}, {'role':'assistant','text':answer}])
    if issues:
        print('\nREVIEW REQUIRED:\n'+'\n'.join(issues))
        return 1
    print('\nPASS: six-turn behavior checks. Review wording and sources in the browser before recording.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
