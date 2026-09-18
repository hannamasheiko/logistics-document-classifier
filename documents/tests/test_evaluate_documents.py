import json
import shutil
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from documents.models import ProcessingAttempt
from documents.tests.test_pipeline import (
    BOL_EVIDENCE,
    BOL_LINES,
    OTHER_EVIDENCE,
    OTHER_LINES,
    completed_response,
    default_extraction_payload,
    make_dual_request,
    make_observations,
    make_text_pdf,
)


class EvaluateDocumentsCommandTests(TestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        self.media_root = tempfile.mkdtemp()
        settings_override = override_settings(MEDIA_ROOT=self.media_root)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)

        self.documents_dir = self.tmp_dir / "documents"
        self.documents_dir.mkdir()

    def write_pdf(self, name: str, lines: list[str]) -> None:
        (self.documents_dir / name).write_bytes(make_text_pdf(lines))

    def write_manifest(self, documents: list[dict]) -> Path:
        manifest_path = self.tmp_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "taxonomy": ["INVOICE", "BOL", "POD", "OTHER"],
                    "documents": documents,
                }
            )
        )
        return manifest_path

    def test_dry_run_makes_no_calls_and_writes_no_report(self) -> None:
        self.write_pdf("bol.pdf", BOL_LINES)
        manifest_path = self.write_manifest(
            [
                {
                    "id": "d1",
                    "path": "documents/bol.pdf",
                    "split": "heldout",
                    "expected_label": "BOL",
                    "expected_outcome": "ACCEPT",
                }
            ]
        )
        output_path = self.tmp_dir / "out.json"

        with patch("documents.management.commands.evaluate_documents.build_default_request") as mock_build:
            out = StringIO()
            call_command(
                "evaluate_documents",
                manifest=manifest_path,
                output=output_path,
                extraction_manifest=self.tmp_dir / "does-not-exist.json",
                stdout=out,
            )

        mock_build.assert_not_called()
        self.assertFalse(output_path.exists())
        self.assertIn("Dry run", out.getvalue())

    def test_live_run_reports_correct_and_incorrect_outcomes_and_cleans_up(self) -> None:
        self.write_pdf("bol.pdf", BOL_LINES)
        self.write_pdf("other.pdf", OTHER_LINES)
        manifest_path = self.write_manifest(
            [
                {
                    "id": "correct-bol",
                    "path": "documents/bol.pdf",
                    "split": "heldout",
                    "expected_label": "BOL",
                    "expected_outcome": "ACCEPT",
                },
                {
                    "id": "wrong-expectation",
                    "path": "documents/other.pdf",
                    "split": "heldout",
                    "expected_label": "INVOICE",
                    "expected_outcome": "ACCEPT",
                },
            ]
        )
        output_path = self.tmp_dir / "out.json"

        bol_observations = make_observations("BOL", BOL_EVIDENCE)
        other_observations = make_observations("OTHER", OTHER_EVIDENCE)
        responses = iter([bol_observations, other_observations])

        def primary_response():
            return completed_response(next(responses))

        request, calls = make_dual_request(primary_response)

        with patch("documents.management.commands.evaluate_documents.build_default_request", return_value=request):
            call_command(
                "evaluate_documents",
                manifest=manifest_path,
                output=output_path,
                extraction_manifest=self.tmp_dir / "does-not-exist.json",
                run_live=True,
            )

        report = json.loads(output_path.read_text())
        self.assertEqual(report["classification"]["counts"]["accepted_correct"], 1)
        self.assertEqual(report["classification"]["counts"]["accepted_incorrect"], 1)
        # BOL and OTHER extraction: OTHER never runs extraction, BOL uses the
        # default all-missing stub since no extraction_response was given.
        self.assertEqual(len(calls["extraction"]), 1)

        # Evaluation attempts must not linger in the shared demo history.
        self.assertEqual(ProcessingAttempt.objects.count(), 0)

    def test_missing_file_is_reported_as_a_technical_failure_not_a_crash(self) -> None:
        manifest_path = self.write_manifest(
            [
                {
                    "id": "ghost",
                    "path": "documents/does-not-exist.pdf",
                    "split": "heldout",
                    "expected_label": "BOL",
                    "expected_outcome": "ACCEPT",
                }
            ]
        )
        output_path = self.tmp_dir / "out.json"

        with patch("documents.management.commands.evaluate_documents.build_default_request") as mock_build:
            mock_build.return_value = lambda parameters: (_ for _ in ()).throw(
                AssertionError("no call expected")
            )
            call_command(
                "evaluate_documents",
                manifest=manifest_path,
                output=output_path,
                extraction_manifest=self.tmp_dir / "does-not-exist.json",
                run_live=True,
            )

        report = json.loads(output_path.read_text())
        self.assertEqual(report["classification"]["counts"]["technical_failure"], 1)
        self.assertEqual(report["classification"]["results"][0]["error"], "missing_file")

    def test_extraction_manifest_is_evaluated_and_reports_mismatches(self) -> None:
        self.write_pdf("bol.pdf", BOL_LINES)
        manifest_path = self.write_manifest(
            [
                {
                    "id": "correct-bol",
                    "path": "documents/bol.pdf",
                    "split": "heldout",
                    "expected_label": "BOL",
                    "expected_outcome": "ACCEPT",
                }
            ]
        )
        extraction_manifest_path = self.tmp_dir / "extraction-manifest.json"
        extraction_manifest_path.write_text(
            json.dumps(
                {
                    "documents": [
                        {
                            "id": "bol-extraction",
                            "path": "documents/bol.pdf",
                            "class": "BOL",
                            "expected_fields": {
                                "bol_number": {"status": "present", "value": "BOL-1"},
                                "carrier": {"status": "missing", "value": None},
                            },
                        }
                    ]
                }
            )
        )
        output_path = self.tmp_dir / "out.json"

        bol_observations = make_observations("BOL", BOL_EVIDENCE)
        actual_extraction_payload = {
            **default_extraction_payload("BOL"),
            "bol_number": {"status": "present", "value": "BOL-1", "evidence": "BOL No: BOL-1"},
        }
        request, calls = make_dual_request(
            lambda: completed_response(bol_observations),
            extraction_response=lambda class_name: completed_response(actual_extraction_payload),
        )

        with patch("documents.management.commands.evaluate_documents.build_default_request", return_value=request):
            call_command(
                "evaluate_documents",
                manifest=manifest_path,
                output=output_path,
                extraction_manifest=extraction_manifest_path,
                run_live=True,
            )

        report = json.loads(output_path.read_text())
        extraction_report = report["extraction"]
        self.assertEqual(extraction_report["total_fields"], 2)
        self.assertEqual(extraction_report["total_matches"], 2)
        self.assertEqual(extraction_report["results"][0]["mismatches"], [])
        self.assertEqual(ProcessingAttempt.objects.count(), 0)
