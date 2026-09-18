# Logistics document classifier

The repository contains a working end-to-end classification flow: upload a
text-layer or scanned PDF, get it classified as `INVOICE`, `BOL`, `POD`, or
`OTHER` (or `UNCERTAIN`/`FAILED`), and review the result, history, and
original PDF through a minimal Django UI. Scanned pages go through local OCR
first; when the primary text/OCR classification cannot accept a result, one
visual fallback call reviews the original PDF's page images directly. An
established combined BOL/POD document is a deliberate semantic `UNCERTAIN`,
never a fallback trigger.

## G0 foundation decisions

- Python 3.14, Django 5.2 LTS, PostgreSQL 18, Psycopg 3, pypdf, and the OpenAI
  Python SDK are pinned in `requirements.txt` and `compose.yaml`.
- One upload is one document with at most 10 pages and 10,000,000 bytes.
- Intake validates PDF content and page structure instead of trusting the file
  extension or MIME type. Encrypted, corrupt, empty, oversized, and over-page-limit
  PDFs are rejected before an attempt or media file is created.
- A structurally valid image-only PDF passes intake. OCR and mixed-page policy
  were designed and tested at G2 (`docs/experiments/scanned-fallback.md`)
  and are wired into production processing.
- Every accepted upload creates a distinct `ProcessingAttempt` and local media
  file, including repeated uploads of identical content.
- The lifecycle begins at `PROCESSING` because validation and durable storage
  precede attempt creation. Terminal states are `ACCEPTED`, `UNCERTAIN`, and
  `FAILED`.
- The model stores normalized primary observations/configuration, nullable final
  result fields, and sanitized failure details. Candidate output does not become
  an accepted label until routing accepts it.
- Fallback observations/metadata are persisted in their own nullable fields
  (`fallback_observations`, `fallback_metadata`), separate from primary
  results, so a fallback failure never overwrites the primary diagnostics
  already recorded for the same attempt. Field extraction (Task 7/G3
  contract, Task 8 implementation) has its own `extraction_status`/
  `extraction_result`/`extraction_metadata` fields for the same reason: an
  extraction failure never changes the classification already recorded.

## Local foundation setup

Create and activate a Python 3.14 virtual environment, then install the pinned
dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

The checked-in Compose defaults are deliberately local-only placeholders. Start
PostgreSQL and apply the schema:

```sh
docker compose up -d
.venv/bin/python manage.py migrate
```

To use custom local values, copy `.env.example` to ignored `.env`, replace its
placeholder values, and export the variables into the shell before running Django:

```sh
set -a
source .env
set +a
```

Run the foundation checks:

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test documents.tests.test_intake
```

Uploaded PDFs are written beneath ignored `media/`. No API call is made by the
Task 2 intake tests, nor by the Task 3/4 routing and pipeline tests, which
fake the OpenAI boundary.

## Running the classifier

OCR requires a local `tesseract` binary (not pip-installable) with the
English data file, e.g. on macOS: `brew install tesseract`.

Classification calls the OpenAI Responses API, so set `OPENAI_API_KEY` in the
shell running the server (never commit it; `.env.example` documents the
expected variable names only):

```sh
export OPENAI_API_KEY=...
.venv/bin/python manage.py runserver
```

Then open `http://127.0.0.1:8000/` to upload a PDF. Uploading redirects to a
result page showing the accepted label and routing score, or the reason for
`UNCERTAIN`/`FAILED`; `/history/` lists every attempt (shared demo history,
no accounts); each result links to the stored original PDF. When a visual
fallback was used, the result page says so and shows which path produced the
accepted label.

For an `ACCEPTED` `BOL`/`POD`/`INVOICE` (never `OTHER`), the result page also
shows extracted fields (value, status, evidence, confidence) per the Task
7/G3 contract (`docs/decisions/field-extraction-contract.md`). A field-level
contradiction (e.g. identical shipper/consignee) is shown explicitly, not
hidden behind a score; an extraction technical failure is reported
separately and never changes the classification above it.

## Evaluation command

`evaluate_documents` (Task 9) runs the real upload -> classify -> route ->
extract pipeline (the same `DocumentUploadForm`/`run_classification`
entrypoints a real request goes through) against a labeled manifest, then
deletes every attempt/file it created so evaluation runs never pollute the
shared demo history. Without `--run-live` it only validates the manifest(s)
and reports what it would run, at no API cost:

```sh
.venv/bin/python manage.py evaluate_documents \
  --manifest evaluation/manifest-v1.json \
  --output evaluation/results/final-v1.json \
  --run-live
```

`--extraction-manifest` (default `evaluation/manifest-extraction.json`)
adds a field-extraction pass over its own set of examples; pass a
non-existent path to skip it. The written report is sanitized (counts and
per-document outcomes only, no raw document text).

## Delivery review (G4)

A full live regression was run against both labeled classification
manifests plus the extraction manifest right before delivery:

- `manifest-v1.json` (22 documents): 16 accepted_correct, 1
  accepted_incorrect, 3 expected_escalation, 2
  semantic_uncertainty_correct, 0 technical_failure.
- `manifest-v2.json` (12 held-out documents): 10 accepted_correct, 0
  incorrect, 1 expected_escalation, 1 semantic_uncertainty_correct, 0
  technical_failure — 100% correct behavior on this split.
- `manifest-extraction.json` (5 documents, 27 fields): 27/27 field
  matches.

Two findings surfaced during this regression and are disclosed rather than
silently patched, per this project's evidence-based, no-silent-tuning
approach:

- **`tuning-incomplete-customs-fragment` (the one accepted_incorrect
  case):** re-inspecting the attempt's own persisted observations (before
  deleting it) showed the visual fallback's evidence for
  `non_target_primary_purpose` was semantically wrong — it described the
  customs-declaration section's *labels* as if their *content* were
  present, when the document explicitly states those sections are
  "unavailable." The evidence string itself was a real, present quote (it
  passed exact-match validation); the error is in interpreting what that
  quote means, which the current evidence-validation contract cannot catch.
  Left as a known limitation rather than tuned around with one example.
- **Extraction manifest methodology gap:** the original
  `g3-invoice-wrong-semantic-role` example reused a document that the
  classification manifest itself expects to `ESCALATE`, so through the real
  pipeline it never reaches `ACCEPTED` and extraction never runs (Task 7's
  own isolated `extract_fields()` check had bypassed classification
  entirely, masking this). Fixed by replacing it with a new,
  genuinely-acceptable fixture,
  `g3-invoice-wrong-semantic-role-accepted.pdf`, that keeps the intended
  placeholder-due-date trap; the manifest and generator were updated and
  the fix was verified live (27/27 above already reflects it).

The setup steps above were also re-verified from a fresh throwaway virtual
environment, and a live browser walkthrough covered all three delivery
scenarios: a text-layer upload with its extraction table, a scanned
document rescued by visual fallback with visual-context extraction, and
reopening a past result/history entry alongside its byte-identical original
PDF.

The 82 automated tests (`documents/tests/`) demonstrate control-flow
correctness — routing rules, retry/validation logic, persistence
boundaries — using faked OpenAI responses; they are not, and are not
presented as, empirical evidence of live model quality. The counts above,
from real API calls against real documents, are that evidence.

## Current limitations

- The routing score is an evidence-completeness signal for the candidate
  class's required features, not a probability of correctness; the same
  applies to the visual fallback's own acceptance check.
- Visual fallback evidence is a free-text human-review description, not a
  machine-verified exact quote, since there is no source string to check an
  image excerpt against — a real, documented reduction in verifiability
  compared to primary text/OCR evidence.
- At most one visual fallback call per attempt; a fallback that itself fails
  technically is a `FAILED` attempt (the primary result stays available for
  diagnostics), not a silent fallback-to-primary or a second escalation.
- Real-world scanned documents (skew, physical photocopying, multi-generation
  artifacts) were not tested; the Task 5/G2 experiment used synthetic
  degradations only (see `docs/experiments/scanned-fallback.md`).
- No content redaction: real uploaded document text/images are sent to the
  OpenAI API as extracted, unlike the masked evaluation corpus in
  `experiments/`.
