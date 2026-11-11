# Ask Bayley: evidence and actions update

This is an incremental update to the existing Ask Bayley project. Keep your .git, .venv, API settings and original assets/bayley.png. No credentials, models, virtual environments or user chat logs are included.

## Install

Back up or commit your current changes first. Extract this update into a separate folder and copy its listed files into your existing ask-bayley checkout, replacing the matching files. Merge the .streamlit/config.toml setting if you already customized that file. Do not replace your whole project folder.

From a terminal inside ask-bayley:

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_models.py
.venv/bin/python -m streamlit run app.py
```

The model check requires BAYLEY_WEBUI_API_KEY in that terminal. On the Mac set BAYLEY_WEBUI_URL=http://localhost:3000 and BAYLEY_MODEL=qwen3:8b if that matches your installation. On DGX use its WebUI URL/key and qwen3:8b or qwen3:32b. Never commit credentials.

Nomic access uses /ollama/api/embed, already verified on your DGX. Laptop permissions may differ. The first embedding request builds a local public-document cache; subsequent questions reuse vectors. If embedding access fails, answers continue with BM25. Live Qwen/Nomic behavior must be tested on your machine: automated tests use controlled fixtures, not your servers.

## Where to revise

| File | What you edit |
|---|---|
| app.py | Example buttons, New conversation, layout, feedback, evidence display, avatar CSS |
| prompts/guide.txt | Tone, identity, evidence and action rules; preserve the JSON output contract |
| bayley.py: resolve_context | Clarifications and remembered term/program |
| bayley.py: retrieve | BM25, semantic retrieval, thresholds, applicability and conflict checks |
| bayley.py: validate_claims | Evidence ID and exact excerpt checks |
| actions.py | Editable IT/email draft templates and mailto links |
| data/entries.json | 26 reviewed notes, aliases, scope, source owner, fact values |
| data/sources.json | Official URLs and checked dates |
| .streamlit/config.toml | Light theme and disabled usage telemetry |
| scripts/check_models.py | Actual endpoint checks on your laptop/DGX |
| tests/test_bayley.py | Regression tests for evidence, context and fallbacks |

Your original PNG is unchanged. CSS displays a face/shoulders crop in the answer body; adjust `.bayley-avatar img` width/transform if needed. The full landing mascot uses `.bayley-mascot img`.

## Knowledge review

Sources checked on 2026-11-11: SFBU Contact Us, SFBU Resources, Academic Calendar, AskIT form, and Our Leadership. These are official-page checks, not interviews or proof that these are the most frequent student questions. Ask students to propose questions and verify the expected answers before using them as a benchmark.

Coverage: president; IT, advising/records, finance, admissions, careers, housing, international support and library contacts; general service hours; clubs/events contact, accommodations, facilities, insurance contact, food pantry and transit contacts; Spring/Summer 2027 standard-semester start, add/drop, withdrawal, exams and end dates. The catalog and handbook remain reference links; their full contents are not indexed. Prior catalog-summary entry is excluded because it was not rechecked in this update.

Every entry has an ID, a source ID, section, source owner, checked date, term, program, effective_from/effective_to, fact_key and fact_value. Null effective dates mean the source did not specify them; the term limits calendar applicability. Owner is the source department, not a claim that someone approved this app. To add a competing version, retain the same fact_key/term/program but use its own ID and fact_value. Conflict detection only handles these explicit structured groups, not arbitrary contradictory prose. Review old notes when source pages change; no automatic refresh is implemented.

## What validation guarantees

The model selects relevant excerpts from retrieved notes. The app checks the IDs and requires an exact excerpt match, then displays the full approved note with a source link to preserve context. This blocks invented text in the displayed claims. It does not prove that the original notes are correct, current or relevant. Retrieval can still fail. Thresholds are initial values, not measured confidence scores.

Model prose is deliberately constrained to evidence selection in this version. Warm wording and action labels live in app.py; changing the model prompt alone does not change all visible messages. No general-purpose model fallback invents missing school facts.

Context is limited to term, year, program and a pending calendar clarification. It is not unrestricted conversational memory. A new season without a year asks for a year instead of assuming. Dates require a program clarification; Pro+ never inherits standard-semester dates. Calendar coverage is intentionally bounded.

Feedback and chat history are session-only. Public document vectors are cached under .cache; questions and credentials are not written there. WebUI/infrastructure retention is outside the app's control. Email and ticket controls prepare/open drafts only. They never send or claim successful submission.

## Demo checks

- "who is the presendate of sfbu" → cited president note.
- "When do classes start?" → term/year clarification; "Spring 2027" → program clarification; "standard semester" → January start note.
- "And when can I drop?" → remembers term/program and retrieves add/drop note.
- "Where do I get Canvas help?" → verified IT contact, editable draft, official form link.
- "Where is the swimming pool?" → insufficient evidence and directory link.
- Test fixtures cover conflicting values, expired evidence, invalid citations, and embedding failure.

## Commit after review

```bash
git diff --stat
git add app.py bayley.py actions.py prompts data scripts tests UPDATE_GUIDE.md requirements.txt .streamlit/config.toml
```

Add `.cache/` to your existing .gitignore before building the index. Keep .venv/ and secrets ignored. Then commit and push normally; pull and restart on DGX.
