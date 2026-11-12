"""Small deterministic conversation helpers; no model or network calls."""
import re


CALENDAR_KEYS = ('season', 'year', 'program', 'calendar_event', 'pending_question')
EVENT_QUESTIONS = {
    'start': 'When do classes start?',
    'drop': 'What is the add/drop deadline?',
    'withdraw': 'What is the withdrawal deadline?',
    'finals': 'When are final examinations?',
    'end': 'When does the semester end?',
    'registration': 'What is the registration deadline?',
    'schedule': 'What are the academic calendar dates?',
}


def without_calendar(context):
    ctx = dict(context)
    for key in CALENDAR_KEYS:
        ctx.pop(key, None)
    if ctx.get('active_topic') == 'calendar':
        ctx.pop('last_question', None)
    ctx['active_topic'] = 'school'
    return ctx


def technical_request(question):
    return bool(re.search(
        r'\b(canvas|askit|login|password|printer|printing|wifi|wi-fi|helpdesk)\b'
        r'|\bhelp\s+desk\b|\bit\s+(support|ticket|help|department)\b',
        question, re.I) or re.search(r'\bIT\b', question))


def retrieval_question(question):
    # Resolve a service alias, not a school fact. Facts still come from evidence.
    return question + ' askit technical' if technical_request(question) else question


def slot_reply(question):
    """Recognize short slot substitutions, not unrelated questions mentioning a year."""
    q = question.casefold()
    if not re.search(r'\b(spring|summer|fall|winter|20\d{2}|standard)\b|pro\s*\+|8[- ]week', q):
        return False
    q = re.sub(r'pro\s*\+|8[- ]week', '', q)
    words = re.findall(r'[a-z0-9]+', q)
    allowed = set('spring summer fall winter standard semester program the in for what how about and then actually no same please instead year term'.split())
    return all(word in allowed or re.fullmatch(r'20\d{2}', word) for word in words)


def calendar_event(question, active=False):
    q = question.casefold()
    academic = bool(re.search(r'\b(class(?:es)?|courses?|semesters?|terms?|academic|enrollment|school)\b', q))
    timing = bool(re.search(r'\b(when|dates?|days?|deadline|schedule|calendar)\b', q))
    # A course mentioned in a Canvas problem does not make it a calendar question.
    if technical_request(question) and not (academic and timing):
        return None
    if re.search(r'\b(withdraw|withdrawal)\b', q) and (timing or academic or active):
        return 'withdraw'
    if re.search(r'\b(drop|add)\b', q) and (academic or re.search(r'add\s*[/ -]\s*drop|drop\s+deadline', q) or (active and timing)):
        return 'drop'
    if re.search(r'\b(finals?|exams?|examinations)\b', q) and timing:
        return 'finals'
    if re.search(r'\b(start|starts|begin|begins|beginning)\b|first\s+day', q) and academic and timing:
        return 'start'
    if re.search(r'\b(end|ends|finish|finishes)\b|last\s+day', q) and academic and timing:
        return 'end'
    if re.search(r'\bregistration\b', q) and timing:
        return 'registration'
    if re.search(r'\bacademic\s+calendar\b', q):
        return 'schedule'
    return None


def resolve_context(question, context):
    """Resolve calendar slots without concatenating old and new term strings."""
    ctx = dict(context)
    q = question.casefold()
    active = ctx.get('active_topic') == 'calendar' or bool(ctx.get('pending_question'))
    event = calendar_event(question, active)
    slots = slot_reply(question)
    if not event and not slots:
        return question, without_calendar(ctx), None
    if not event and slots:
        event = ctx.get('calendar_event') if active else None
    seasons = re.findall(r'\b(spring|summer|fall|winter)\b', q)
    years = re.findall(r'\b20\d{2}\b', q)
    if len(set(seasons)) > 1 or len(set(years)) > 1:
        ctx = without_calendar(ctx)
        return question, ctx, 'Please ask about one term and year at a time.'
    program = None
    if re.search(r'\bpro\s*\+|\b8[- ]week', q):
        program = 'Pro+'
    elif re.search(r'\bstandard\b', q):
        program = 'standard semester'
    new_term = (seasons and seasons[0] != ctx.get('season')) or (years and years[0] != ctx.get('year'))
    completing = bool(ctx.get('pending_question')) and slots
    if new_term and not program and not completing:
        ctx.pop('program', None)
    if seasons:
        if seasons[0] != ctx.get('season') and not years:
            ctx.pop('year', None)
        ctx['season'] = seasons[0]
    if years:
        ctx['year'] = years[0]
    if program:
        ctx['program'] = program
    ctx['active_topic'] = 'calendar'
    ctx.pop('request_context', None)
    ctx.pop('last_question', None)
    if not event:
        ctx.pop('calendar_event', None)
        ctx.pop('pending_question', None)
        return question, ctx, 'What would you like to know about that term—for example, when classes start?'
    ctx['calendar_event'] = event
    query = EVENT_QUESTIONS[event]
    ctx['pending_question'] = query
    if not ctx.get('season') or not ctx.get('year'):
        if ctx.get('season'):
            return query, ctx, f'Which year do you mean for {ctx["season"].title()}?'
        if ctx.get('year'):
            return query, ctx, f'Which term in {ctx["year"]} do you mean?'
        return query, ctx, 'Which term and year do you mean—for example, Spring 2027?'
    query += ' ' + ctx['season'] + ' ' + ctx['year']
    if not ctx.get('program'):
        return query, ctx, 'Is this for a standard semester or a Pro+ program?'
    ctx.pop('pending_question', None)
    return query, ctx, None


def draft_requested(question):
    return bool(re.search(r'\b(draft|write|compose|prepare)\b.{0,60}\b(email|e-mail|message|ticket|request)\b', question, re.I))


def followup_question(question):
    # Lowercase "it" is a pronoun; uppercase IT is the department.
    return bool(re.search(r'\b(them|their|that|same)\b', question, re.I)
                or re.search(r'\b(?:it|It)\b', question)
                or re.search(r'^(and\b|what about\b|how about\b|the error\b|I tried\b)', question, re.I))


def has_topic(question, entries):
    if technical_request(question):
        return True
    return any(re.search(r'\b' + re.escape(k) + r'\b', question, re.I)
               for e in entries for k in e['keywords'] if len(k) > 3)
