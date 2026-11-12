# Ask Bayley core fixes

Baseline: the applied `ask-bayley-routing-update.zip`, with no later code edits.
This is an incremental patch for the existing project.

## Apply and start

Stop the running app with Ctrl+C in its terminal. Extract this ZIP into Downloads;
the patch should be at `~/Downloads/ask-bayley-core-fixes/core-fixes.patch`.
Use a terminal inside your existing `ask-bayley` project, and check compatibility:

```bash
git apply --check "$HOME/Downloads/ask-bayley-core-fixes/core-fixes.patch"
```

If Git reports a conflict, stop and share the error. Your files may contain changes
beyond the routing package. Do not force the patch or replace the whole project.
If the check succeeds, apply it:

```bash
git apply "$HOME/Downloads/ask-bayley-core-fixes/core-fixes.patch"
```

Then run the checks and start the app:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Stop if any test fails. Otherwise:

```bash
.venv/bin/python run.py
```

The launcher reuses the WebUI address/API key in its environment, or asks for
them. It never needs the key committed to Git. Mac default: localhost:3000;
DGX default: localhost:8080. Authentication and model visibility are checked at
launch; actual generation is identified in each reply's production details.
Click **New conversation** after updating to clear older conversation state.
No additional dependencies, models, or source downloads are needed.

## Fixed behavior and file map

| File | Change |
|---|---|
| `conversation.py` (new) | Calendar intent and term/program/event slots; technical-service aliases; follow-up and draft-request helpers. No network calls. |
| `bayley.py` | Routes single questions, retrieves event-specific evidence, clears stale topic context, and prepares drafts using the student's original issue and a verified contact. |
| `app.py` | Supplies the original issue to the draft, expands explicitly requested drafts, and clears all draft widgets on New conversation. |
| `tests/test_core_fixes.py` (new) | Routing, term changes, applicability, recipient selection, draft details, and model/fallback regression cases. |
| `tests/test_ui_core.py` (new) | Real Streamlit chat widgets, editable drafts, feedback reruns, and conversation reset. |

The existing mascot, prompt, source data, credentials, and dependencies are
unchanged. This guide describes the newest behavior; earlier update guides
describe their respective releases.

## Try these on your laptop or DGX

Use New conversation between independent tests. Keep the same conversation for
steps joined by an arrow.

| Test | What to type | Expected behavior |
|---|---|---|
| IT routing | How do I start an IT ticket? | IT contact and official AskIT form; no academic-term question. |
| Printer routing | Who can help me add a printer? | IT evidence; no add/drop or calendar question. |
| Study advice | How do I prepare for my exams? | General study guidance. With a working API, production details identify the configured Qwen model. No exam-date guess. |
| Calendar follow-up | When do standard-semester classes start in Spring 2027? → What about Summer 2027? → standard semester | Spring start evidence, program clarification for Summer, then Summer start evidence. No combined-term conflict. |
| Event follow-up | After the previous sequence: And when can I drop? | Summer 2027 standard-semester add/drop evidence, not the start date. |
| Missing coverage | When do Pro+ classes start in Spring 2027? | Explicit coverage gap and official calendar link; no standard-semester substitution. |
| Topic switch | When do classes start? → Where do I get Canvas help? → How do I contact them? | Calendar clarification gives way to IT. The follow-up still concerns IT; no stale term/program label. |
| Useful draft | Canvas says access denied when I open my course. → Please draft an email to them. | Editable IT draft includes the original Canvas problem. Nothing is sent. |
| Additional detail | I cannot log into Canvas. → It says access denied. → Draft an email to IT. | Draft includes both the original problem and the error detail. |
| Clean reset | Edit a draft → New conversation → The printer shows an error. → Draft an email to IT. | New draft contains the printer issue, not the edited Canvas text. |
| Configuration | What model are you? | Reads the configured model name; does not claim that key presence proves successful generation. |

For each school answer, open the citation and confirm the note still matches the
official page before recording. Check one real Qwen reply and one hybrid-retrieval
reply in **How this answer was produced**. An honest fallback is useful, but it
does not prove that a model request succeeded.

## Verification and limits

51 automated tests passed locally: the previous 26 regressions, 24 new core
regressions, and one multi-step Streamlit interface test. Model response/failure
paths use controlled mocks. The UI test uses source-note mode and verifies that
feedback or draft editing does not generate a duplicate answer.

Packaging checks apply the patch to a clean copy of the routing baseline,
compare every changed file, and rerun the suite. ZIP integrity is checked.
Live Qwen/Nomic behavior, DGX latency, and browser scrolling still require a check
on your computer. These tests are regression evidence, not an answer-accuracy
benchmark or a guarantee that arbitrary wording is handled.

Knowledge coverage remains 39 curated notes; the full catalog and handbook are
not indexed. Multi-question handling and Gemma screenshot uploads are deferred.
Routing and safety checks use bounded rules; citation validation checks excerpts,
IDs, and selected output constraints rather than proving semantic truth. Draft
recipient selection uses the supported verified contacts; unknown recipients or
missing problem descriptions trigger clarification. No emails or tickets are sent.

## Commit after the checks pass

Review `git status --short` first. These commands stage only this update's files:

```bash
git add app.py bayley.py conversation.py tests/test_core_fixes.py tests/test_ui_core.py CORE_FIXES.md
git diff --cached --stat
git commit -m "Fix Bayley routing, calendar follow-ups, and request drafts"
git push origin main
```

On DGX, stop the old app, enter `~/ask-bayley`, and run `git pull --ff-only`.
If Git reports an error, stop and share it. Then run the same tests and launcher
using that machine's project `.venv` and WebUI credentials.
