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
  already recorded for the same attempt. Field-extraction persistence is
  deferred until G3.

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
