"""Draft helpers. No email or ticket is sent by this module."""
from urllib.parse import urlencode

def draft(question,entry):
    department=entry['title']
    subject='Student support request — '+department
    body=f'Hello {department},\n\nI would appreciate help with the following:\n{question}\n\n'
    if entry['id']=='it':
        body+='Affected service: [fill in]\nError message: [fill in]\nWhen it happened: [fill in]\nSteps already tried: [fill in]\n\n'
    body+='Could you please advise on the next step?\n\nThank you,\n[Your name]'
    return subject,body

def mailto(address,subject,body):
    return 'mailto:'+address+'?'+urlencode({'subject':subject,'body':body})
