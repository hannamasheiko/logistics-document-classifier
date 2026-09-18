"""Task 9 delivery evaluation: runs the real production upload -> classify ->
route -> extract pipeline against a labeled manifest and writes a sanitized
report. Never used to establish thresholds; it only checks the already-frozen
production contract against expected labels/outcomes/fields.

Live calls only happen with --run-live. Without it, the command validates
both manifests and reports what it would run, without spending anything.
The regular Django test suite never passes --run-live, so this command's
live path is never exercised by `manage.py test`.

Every evaluated document is uploaded and processed through the same
DocumentUploadForm/run_classification entrypoints a real user request goes
through (not a reimplementation of the pipeline), then deleted afterward so
the shared demo history/media stay free of evaluation runs.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from documents.forms import DocumentUploadForm
from documents.models import ProcessingAttempt
from documents.services.processing import build_default_request, run_classification


VALID_LABELS = {"INVOICE", "BOL", "POD", "OTHER"}
VALID_OUTCOMES = {"ACCEPT", "ESCALATE", "UNCERTAIN_NO_FALLBACK"}


def load_classification_manifest(path: Path) -> list[dict]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise CommandError(f"Unsupported manifest schema version in {path}.")
    if set(manifest.get("taxonomy", [])) != VALID_LABELS:
        raise CommandError(f"Manifest taxonomy does not match the agreed classes in {path}.")
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise CommandError(f"Manifest has no documents: {path}.")
    for document in documents:
        if document.get("expected_outcome") not in VALID_OUTCOMES:
            raise CommandError(f"Unknown expected_outcome for {document.get('id')} in {path}.")
    return documents


def load_extraction_manifest(path: Path) -> list[dict]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise CommandError(f"Extraction manifest has no documents: {path}.")
    return documents


def resolve_path(manifest_path: Path, relative_path: str) -> Path:
    return (manifest_path.parent / relative_path).resolve()


class Command(BaseCommand):
    help = (
        "Run the real upload/classification/extraction pipeline against a "
        "labeled manifest and write a sanitized JSON report."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--manifest", required=True, type=Path)
        parser.add_argument("--output", required=True, type=Path)
        parser.add_argument(
            "--extraction-manifest",
            type=Path,
            default=Path("evaluation/manifest-extraction.json"),
            help="Set to a non-existent path to skip the extraction pass entirely.",
        )
        parser.add_argument(
            "--run-live",
            action="store_true",
            help=(
                "Actually call the OpenAI API. Without this flag, the command "
                "only validates the manifests and reports what it would run."
            ),
        )

    def handle(self, *args, **options) -> None:
        manifest_path: Path = options["manifest"]
        extraction_manifest_path: Path = options["extraction_manifest"]
        output_path: Path = options["output"]
        run_live: bool = options["run_live"]

        classification_documents = load_classification_manifest(manifest_path)
        extraction_documents = (
            load_extraction_manifest(extraction_manifest_path)
            if extraction_manifest_path.exists()
            else []
        )

        if not run_live:
            self.stdout.write(
                f"Dry run: {len(classification_documents)} classification document(s) "
                f"and {len(extraction_documents)} extraction example(s) validated. "
                "Pass --run-live to actually call the OpenAI API."
            )
            return

        request = build_default_request()

        classification_report = self._evaluate_classification(
            classification_documents, manifest_path, request
        )
        extraction_report = self._evaluate_extraction(
            extraction_documents, extraction_manifest_path, request
        )

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "manifest": str(manifest_path),
            "extraction_manifest": str(extraction_manifest_path) if extraction_documents else None,
            "classification": classification_report,
            "extraction": extraction_report,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.stdout.write(self.style.SUCCESS(f"Report written to {output_path}"))

    def _run_pipeline(self, pdf_path: Path, request):
        """Uploads and processes one PDF through the real production
        entrypoints. Returns (attempt, error_category); on error, attempt is
        None and nothing is persisted (an intake rejection creates no row,
        matching Task 2's own guarantee)."""
        if not pdf_path.is_file():
            return None, "missing_file"
        with pdf_path.open("rb") as source:
            upload = SimpleUploadedFile(pdf_path.name, source.read(), content_type="application/pdf")
        form = DocumentUploadForm(files={"document": upload})
        if not form.is_valid():
            return None, "intake_rejected"
        attempt = form.save()
        run_classification(attempt, request=request)
        return attempt, None

    @staticmethod
    def _delete_attempt(attempt: ProcessingAttempt) -> None:
        if attempt.original_file:
            attempt.original_file.delete(save=False)
        attempt.delete()

    def _evaluate_classification(self, documents, manifest_path, request) -> dict:
        counts = {
            "accepted_correct": 0,
            "accepted_incorrect": 0,
            "expected_escalation": 0,
            "unnecessary_escalation": 0,
            "semantic_uncertainty_correct": 0,
            "semantic_uncertainty_incorrect": 0,
            "technical_failure": 0,
        }
        results = []
        for document in documents:
            pdf_path = resolve_path(manifest_path, document["path"])
            attempt, error = self._run_pipeline(pdf_path, request)
            if attempt is None:
                counts["technical_failure"] += 1
                results.append({"id": document["id"], "split": document.get("split"), "error": error})
                continue

            expected_label = document.get("expected_label")
            expected_outcome = document["expected_outcome"]
            entry = {
                "id": document["id"],
                "split": document.get("split"),
                "expected_label": expected_label,
                "expected_outcome": expected_outcome,
                "status": attempt.status,
                "accepted_label": attempt.accepted_label,
                "routing_score": attempt.routing_score,
                "score_method": attempt.score_method,
                "used_fallback": attempt.fallback_observations is not None,
            }

            if attempt.status == ProcessingAttempt.Status.ACCEPTED:
                if expected_outcome == "ACCEPT" and attempt.accepted_label == expected_label:
                    counts["accepted_correct"] += 1
                else:
                    counts["accepted_incorrect"] += 1
            elif attempt.status == ProcessingAttempt.Status.UNCERTAIN:
                routing = (attempt.fallback_metadata or attempt.primary_metadata or {}).get(
                    "routing", {}
                )
                reason = routing.get("reason")
                entry["routing_reason"] = reason
                if expected_outcome == "UNCERTAIN_NO_FALLBACK" and reason == "established_combined_bol_pod":
                    counts["semantic_uncertainty_correct"] += 1
                elif expected_outcome == "UNCERTAIN_NO_FALLBACK":
                    counts["semantic_uncertainty_incorrect"] += 1
                elif expected_outcome == "ESCALATE":
                    counts["expected_escalation"] += 1
                else:
                    counts["unnecessary_escalation"] += 1
            else:
                entry["failure_stage"] = attempt.failure_stage
                entry["failure_category"] = attempt.failure_category
                counts["technical_failure"] += 1

            results.append(entry)
            self._delete_attempt(attempt)

        return {"counts": counts, "results": results}

    def _evaluate_extraction(self, documents, manifest_path, request) -> dict | None:
        if not documents:
            return None

        total_fields = 0
        total_matches = 0
        results = []
        for document in documents:
            pdf_path = resolve_path(manifest_path, document["path"])
            attempt, error = self._run_pipeline(pdf_path, request)
            if attempt is None:
                results.append({"id": document["id"], "error": error})
                continue

            expected_fields = document["expected_fields"]
            actual_fields = attempt.extraction_result or {}
            mismatches = []
            for field_name, expected in expected_fields.items():
                total_fields += 1
                actual = actual_fields.get(field_name, {})
                if actual.get("status") == expected["status"] and actual.get("value") == expected.get(
                    "value"
                ):
                    total_matches += 1
                else:
                    mismatches.append(
                        {
                            "field": field_name,
                            "expected": expected,
                            "actual": {"status": actual.get("status"), "value": actual.get("value")},
                        }
                    )

            results.append(
                {
                    "id": document["id"],
                    "class": document["class"],
                    "extraction_status": attempt.extraction_status,
                    "field_total": len(expected_fields),
                    "field_matches": len(expected_fields) - len(mismatches),
                    "mismatches": mismatches,
                }
            )
            self._delete_attempt(attempt)

        return {"total_fields": total_fields, "total_matches": total_matches, "results": results}
