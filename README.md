# Logistics document classifier

The repository currently contains the Task 2 application foundation: a Django
project, PostgreSQL-backed processing attempts, local PDF storage, and validated
PDF intake. It is not yet a classifier demo; text classification and routing are
introduced in Tasks 2E–4.

## G0 foundation decisions

- Python 3.14, Django 5.2 LTS, PostgreSQL 18, Psycopg 3, pypdf, and the OpenAI
  Python SDK are pinned in `requirements.txt` and `compose.yaml`.
- One upload is one document with at most 10 pages and 10,000,000 bytes.
- Intake validates PDF content and page structure instead of trusting the file
  extension or MIME type. Encrypted, corrupt, empty, oversized, and over-page-limit
  PDFs are rejected before an attempt or media file is created.
- A structurally valid image-only PDF passes intake. OCR and mixed-page policy are
  deferred to G2.
- Every accepted upload creates a distinct `ProcessingAttempt` and local media
  file, including repeated uploads of identical content.
- The lifecycle begins at `PROCESSING` because validation and durable storage
  precede attempt creation. Terminal states are `ACCEPTED`, `UNCERTAIN`, and
  `FAILED`.
- The model stores normalized primary observations/configuration, nullable final
  result fields, and sanitized failure details. Candidate output does not become
  an accepted label until routing accepts it.
- Fallback-specific persistence is deferred until G2 defines the visual contract.
  Field-extraction persistence is deferred until G3.

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
Task 2 intake tests.
