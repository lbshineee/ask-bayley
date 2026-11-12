"""A fast, explicitly sourced campus starter guide; no inference required."""
import re
from conversation import without_calendar, technical_request


def guide_requested(question):
    q = question.casefold().strip(' .!?')
    q = q.replace('orentation', 'orientation')
    q = q.replace('anthing', 'anything').replace('kknow', 'know')
    # Match onboarding requests, not orientation dates, medical specifics,
    # assignment questions, or a specific IT problem mentioning orientation.
    if technical_request(q):
        return False
    if re.search(r'\b(missed|miss|missing)\b.{0,25}\borientation\b', q):
        return not re.search(r'\b(when|date|deadline|quiz)\b', q)
    if re.fullmatch(r'(?:hi[,! ]+|hello[,! ]+)?(?:is there |are there )?(?:anything|anything else|something|things) (?:that )?(?:i|we) should know(?: about (?:sfbu|school|campus))?', q):
        return True
    if re.fullmatch(r'(?:should|do) (?:i|we) (?:need to )?know anything(?: about (?:sfbu|school|campus))?', q):
        return True
    if re.fullmatch(r'what (?:should|do) (?:i|we) (?:need to )?know(?: about (?:sfbu|school|campus)| as a new student)?', q):
        return True
    return bool(re.search(r'\bnew student\b', q) and re.search(
        r'\b(what should|what do i need|anything|getting started|where do i start|guide)\b', q))


def guide_reply(question, entries, context):
    ctx = without_calendar(context)
    ctx.pop('request_context', None)
    ctx.pop('last_question', None)
    ctx['active_topic'] = 'onboarding'
    ids = ['guide-orientation', 'guide-address', 'guide-buildings',
           'guide-break', 'guide-courses', 'guide-tasks', 'guide-it']
    available = {e['id']: e for e in entries}
    selected = [available[i] for i in ids if i in available]
    # Keep the overview faithful and quick; do not ask an LLM to add details.
    welcome = ('Welcome to SFBU! No worries—I’ve got you. 😊 '
               'I’m Bayley the Bayhawk, your SFBU student-guide prototype. '
               'Let’s get you started.')
    return {'role':'assistant', 'question':question, 'status':'onboarding',
            'context':ctx, 'show_calendar_context':False,
            'text':welcome, 'entries':selected, 'paragraphs':[],
            'mode':'Campus starter guide · official links + user-verified campus notes · no model request',
            'closing':'You don’t have to remember everything—you can always come back and ask me. '
                      'I’ll tell you when I don’t have enough information.\n\n'
                      '**What would help most right now: checking when classes start, getting into Canvas, or finding the right office?**'}
