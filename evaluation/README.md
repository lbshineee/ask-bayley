# Ask Bayley: 120-scenario evaluation

This adds **120 synthetic scenarios, containing 148 individual prompts**, in ten
categories. Twelve representative scenarios form a quick smoke test. It adds no
models, changes no app behavior and does not expand the knowledge base.

These are candidate evaluation cases, not 120 proven correct answers. Expected
facts are copied from the existing curated source notes. Re-check the official
pages before presenting claims about current dates, people or services.

## What the counts mean

| Evidence | Meaning |
|---|---|
| The previous release's 51 regression tests | Software behavior under controlled conditions; includes mocked model paths and one Streamlit UI workflow. |
| 120 scenarios / 148 prompts | A broader evaluation set, including different wording and follow-up conversations. |
| Automatic checks | Expected route/status, evidence IDs, selected context rules and other observable constraints. |
| Human review | Whether the answer actually solves the question, is factually supported, and makes the right clarification or abstention. |
| Live DGX run | Actual local-model requests and observed backend latency on the specified machine. |

Do not add these numbers together or call an automatic-check pass "answer accuracy."
The eight tests of this runner itself are also separate from the app's tests.

## Run from the existing ask-bayley project

Offline, without an API key or models:

```bash
.venv/bin/python scripts/run_evaluation.py --mode offline
```

Start with a small real-model run on DGX:

```bash
.venv/bin/python scripts/run_evaluation.py --mode live --smoke --webui-url http://localhost:8080 --run-note "DGX Spark, one evaluation session"
```

On your Mac, use `http://localhost:3000` if that is your Open WebUI address. The
runner reuses `BAYLEY_WEBUI_API_KEY` from this terminal or asks for it with hidden
input. Both Qwen3:8b and nomic-embed-text:v1.5 must be visible. It does not install
or download a model. An API/model-list check is not proof that inference succeeds.

After reviewing the smoke run, run all 120 scenarios sequentially:

```bash
.venv/bin/python scripts/run_evaluation.py --mode live --webui-url http://localhost:8080 --run-note "DGX Spark, full sequential evaluation"
```

Ctrl+C stops the run and retains partial results. There are no automatic retries
or background jobs. The existing client may take up to its 90-second request
timeout. With 148 prompts, the complete live run may take much longer than a few
minutes. It is reasonable to present a smaller honestly reviewed sample if time
is limited. `--limit 20` runs the first 20 cases, which are not category-balanced;
use `--smoke` for the representative subset.

Each run gets a new directory under `evaluation/results/`:

- `results.jsonl`: actual responses, returned evidence IDs and conversation state.
- `review.csv`: readable questions, answers, source links and blank human grades.
- `summary.json`: automatic-check counts and, in live mode, latency by request path.
- `metadata.json`: model, machine, source/code hashes and cache state.

No API key is included. Only these synthetic evaluation conversations are written.
The runner does not collect students' real chats. The results directory has its
own Git ignore rule. Review data before sharing it.

Exit code 1 means at least one completed case needs review; it does not mean the
runner crashed. Exit code 2 means setup failed. Exit code 130 means interrupted.

## Human grading

Use `question_bank.csv` for manual UI tests, and `review.csv` to grade actual runs.
For every scenario, inspect all turns together. The same case keeps conversation
state; the next case starts empty. Mark `human_verdict` as one of:

- `correct_answer`: answers the asked question with evidence supporting every school claim.
- `correct_clarification`: asks for genuinely missing information without guessing.
- `correct_abstention`: identifies an unavailable fact and offers an appropriate next step.
- `correct_refusal`: handles the boundary safely and directly.
- `helpful_draft`: preserves the student's issue, uses the right verified contact, and claims no sending.
- `incorrect`, `irrelevant`, or `technical_failure`.

Record citation support and usefulness separately. A related link does not prove
the claim. For example, general office hours do not establish food-pantry hours.
An ISS contact does not establish OPT eligibility or an immigration deadline.
Grade against sources and the explicit rubric, not another model's opinion alone.

Report separately:

1. Correct answers / answerable cases reviewed.
2. Appropriate clarifications and abstentions / cases needing them.
3. Unsupported claims and wrong-office handoffs.
4. Correctly preserved follow-ups and useful drafts.
5. Median and p95 backend response time, with sample size and hardware.

For a small smoke run, median and slowest response are easier to interpret than
p95. Instant identity/refusal responses are separated from model-backed turns.
Source-note fallbacks are counted; they are not proof of model success. Latencies
are backend time, not full browser render time. Offline timings are deliberately
excluded from performance summaries. Repeated variants are related cases, not
independent evidence about all university questions. This is a development set;
if tuned against it, use fresh student-authored questions as a held-out check.

## Quality versus load

This runner intentionally sends one request at a time. Do not launch 200 requests
simultaneously on the shared Sparks. First establish correctness. If a load test
fits the allocated machine time, test 1, then 2, then 4 separate sessions with a
small fixed question set, unique session state, warmed document embeddings, and
recorded errors/latencies. Stop increasing load when errors or waits become
unacceptable. A burst of 200 queued requests is not a useful answer-quality test.

## Presentation use

Keep the three-minute recording focused on one student story. On the evidence
slide show three readable, real excerpts: a cited answer; a context-preserving
follow-up; and a missing-evidence response with a useful next step. A separate
Q&A appendix can show the ten category checklist and links to reviewed results.
Do not manufacture screenshots or present offline source-note replies as Qwen
responses. If the recording skips waits, disclose that and show the actual timing.

The supplied `OBSERVED_FINDINGS.md` records offline findings. A live model may
handle some irrelevant retrieved evidence better, but it must be tested. Passing
reference checks does not prove semantic correctness or immunity to hallucination.

## File map and validation

- `evaluation/cases.json`: cases, expectations and copied reference notes.
- `evaluation/question_bank.csv`: printable/reviewable test list.
- `evaluation/baseline_sha256.json`: expected runtime and data version.
- `scripts/run_evaluation.py`: sequential offline/live runner.
- `evaluation/test_runner.py`: tests for the evaluation tooling.

```bash
.venv/bin/python -m unittest discover -s evaluation -p 'test_*.py' -v
```

If you change the application, the runner records the hash mismatch rather than
silently treating the version as identical. It does not overwrite app files or
reuse old results. Browser scrolling, visual layout and manual draft controls
still need separate UI testing.
