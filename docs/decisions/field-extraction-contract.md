# Field-extraction contract (Task 7 / G3)

## Status

Agreed contract, reviewed point by point with the user. This is a design checkpoint, not implementation: no `documents/` code changes. Task 8 implements this contract as written; it does not reopen these decisions without a concrete found problem.

Field extraction with per-field confidence was named as an **optional** part of the original assignment. It is a separate, narrower layer on top of the already-complete document-level classification (Tasks 1–6): extraction only ever runs for an already-`ACCEPTED` document, and never changes that classification.

## Scope

Extraction runs only when the document was `ACCEPTED` (a real candidate class was accepted by primary or visual-fallback routing). It never runs for `OTHER` or for semantic `UNCERTAIN`. No new extraction-specific classification fallback exists: extraction reuses whatever routing already accepted.

## Class-specific field schema

Approximately 3–5 fields per class was the starting guideline; BOL ended up at 6 fields because `destination` is already part of the frozen classification feature `bol_shipment_structure` ("carrier plus shipper/consignee **or origin/destination** plus cargo/packages/weight"), so extracting it explicitly as a field is close to free and avoids having to redo this later for an already-recognized core fact. The same reasoning extended `destination` to POD, since confirming delivery *at the correct address* is as central to proof-of-delivery as confirming who received it and when.

| Class | Field | Value type |
|---|---|---|
| BOL | `bol_number` | identifier |
| BOL | `carrier` | string |
| BOL | `shipper` | string |
| BOL | `consignee` | string |
| BOL | `ship_date` | date |
| BOL | `destination` | string |
| POD | `tracking_number` | identifier |
| POD | `carrier` | string |
| POD | `recipient_name` | string |
| POD | `delivery_date` | date |
| POD | `destination` | string |
| INVOICE | `invoice_number` | identifier |
| INVOICE | `provider` | string |
| INVOICE | `bill_to` | string |
| INVOICE | `amount_due` | amount |
| INVOICE | `due_date` | date |

`tracking_number` on POD is defined broadly: whatever the document's own reference/tracking identifier is, however it is labeled on that specific template (e.g. "Certificate:", "Receipt number:", "Waybill:"), not literally the word "tracking."

`OTHER` has no extraction schema; extraction is never attempted for it.

## Structured field result

```json
{
  "status": "present" | "missing" | "unclear",
  "value": "<value as printed, or null>",
  "evidence": "<exact quote (text/OCR) or free-text description (visual), or null>"
}
```

- `present`: a specific value was found. `value` holds it as printed (no silent normalization — see validators below). `evidence` is a short exact quote for text/OCR context, following the same provenance rule already used for classification evidence; for visual-fallback context it is a free-text human-review description, exactly like visual classification evidence, since there is no source string to check an image excerpt against.
- `missing`: the document genuinely does not contain this information.
- `unclear`: something is present but cannot be confidently read as a real value (illegible, ambiguous, or a placeholder rather than genuine content — see the wrong-semantic-role example below). `value` and `evidence` are `null`.

An evidence-provenance failure for a `present` field (a quote that is not an exact substring of the supplied text) is a technical extraction failure, exactly like an evidence-provenance failure in classification — it is never silently downgraded to `unclear`.

## Deterministic validators

Only where a validator adds real value; no validator is invented just to have one for every field.

- **Date fields** (`ship_date`, `delivery_date`, `due_date`): parseable as a real calendar date. A payment-terms phrase like "Net 21" is not a date and must not be extracted as one; if no actual date is printed, the field is `missing`, not a misread of the terms.
- **Amount field** (`amount_due`): parseable as a currency amount.
- **Identifier fields** (`bol_number`, `tracking_number`, `invoice_number`): only a light plausibility check — non-empty (already implied by `present`) and not implausibly long (a full paragraph accidentally captured is not an identifier). No format/checksum rule: real-world identifier formats vary too much between carriers and companies (e.g. different courier services use completely different tracking-number conventions) to justify one shared pattern; inventing one would fit our specific examples, not reality.
- **Free-text fields** (`carrier`, `shipper`, `consignee`, `recipient_name`, `destination`, `provider`, `bill_to`): no format validator.

A validator result is never written back over the raw `value`. Validation is a separate, explicit record: `{"valid": bool, "reason": "...", "normalized_value": "..." | null}`. A valid format never implies a correct semantic role — see the wrong-semantic-role example.

### Consistency checks

Defined only where the schema has a natural pair of distinct-party fields, and extended to a second class for the same structural reason:

- BOL: `shipper == consignee` → flagged as a contradiction.
- INVOICE: `provider == bill_to` → flagged as a contradiction (a provider is not expected to bill itself).
- POD has no equivalent field pair, so no consistency check is defined for it. Not every class needs one.

**What a flagged contradiction actually does:** both values stay stored exactly as extracted — the contract does not guess which one (if either) is wrong, and does not discard either. Both fields' confidence drops to `0.0`, since the contradiction casts doubt on the pair together, not on one field over the other. The contradiction is surfaced explicitly (e.g. `contradiction_with: ["consignee"]`), never hidden behind a bare low number. None of this touches the document's already-`ACCEPTED` classification status or label.

## Field-confidence formula

Discrete, explainable levels rather than a weighted score, matching the project's existing preference for backend-computed, explainable signals over an opaque number. The model never reports this itself — it only reports `status`/`value`/`evidence`, exactly as it never reports a classification score.

- `status != "present"` → confidence = `null` (not applicable).
- `status == "present"`:
  - a contradiction was flagged for this field → `0.0`, regardless of validator result.
  - the field has a validator and it failed (invalid format) → `0.5`.
  - the validator passed, or the field has no validator (free text) → `1.0`.

This score describes extraction-evidence quality, not a probability of correctness, exactly like the classification routing score.

## Execution/input rule

Extraction reuses whichever context already produced the `ACCEPTED` result — no separate text/visual/call-strategy comparison, and no new extraction-specific fallback:

- If primary text/OCR classification was accepted, extraction runs on that same `document_text`, with exact-quote evidence validation.
- If visual fallback was what accepted the document, extraction runs on the same page images, with free-text evidence, exactly like visual classification.

If the available context is insufficient for a given field, that field is `missing`/`unclear`; it never triggers a new classification escalation.

## Persistence and UI representation

- `extraction_status`: `not_applicable` (never run, for `OTHER`/`UNCERTAIN`) | `completed` | `unavailable` (technical failure of the extraction call) — kept separate from the document's own `status`, so an extraction failure can never retroactively change an already-`ACCEPTED` classification.
- `extraction_result` (only when `completed`): a per-field record of `{value, status, evidence, validation, confidence, contradiction_with}`.
- `extraction_metadata`: which context was used (primary text/OCR vs. visual), plus model/prompt/schema identifiers, mirroring classification metadata.
- On `unavailable`: a separate failure category/reason, on the same pattern as classification technical failures.
- **No partial extraction.** One structured-output call returns every field of the class's schema at once (`present`/`missing`/`unclear` for each), exactly like classification already returns every feature in one call. There is no intermediate "half the fields extracted" state by design; a technical failure makes the whole result `unavailable`, not a partial one.
- UI: when `completed`, the result page shows a field table (value, status, confidence, evidence, contradiction warning if any); when `unavailable`, a short note that extraction technically failed and that the accepted classification above is unaffected; when `not_applicable`, no extraction section is shown at all.

## Expected examples

Hand-prepared by reading the actual document text, not generated or verified by any LLM call, and not a tuning/held-out split — stored in `evaluation/manifest-extraction.json`, reusing already-approved classification fixtures plus one new synthetic BOL built specifically for the contradiction case (`g3-extraction-contradiction-bol.pdf`).

| Example | Class | What it covers |
|---|---|---|
| `g3-bol-known-and-missing` | BOL | Clean known values plus one genuinely missing field (`ship_date`) |
| `g3-pod-all-present` | POD | All fields present, including a non-literally-named `tracking_number` |
| `g3-invoice-terms-not-a-date` | INVOICE | `due_date` must stay `missing` when only payment terms ("Net 21"), not a date, are printed |
| `g3-invoice-wrong-semantic-role` | INVOICE | `Provider: [partially unreadable]` is a placeholder, not a real value — must be `unclear`, not `present` with the placeholder text |
| `g3-bol-shipper-consignee-contradiction` | BOL | `shipper == consignee` — both kept, both confidence `0.0`, flagged explicitly |

## Limitations

- Identifier validators are deliberately format-agnostic; a garbled OCR identifier that happens to be a plausible length/shape will still pass the light plausibility check. This is a known, accepted gap, not an oversight.
- The consistency checks cover only same-value contradictions on the two fields pairs that exist in this schema; no broader cross-field or cross-document consistency checking is in scope.
- Examples are small and hand-picked for specific behaviors (missing, wrong-semantic-role, contradiction); this is not a representative accuracy evaluation of extraction quality, the same way the small G1/G2 example sets were not.
- Visual-fallback extraction evidence is a human-review description, not a machine-verified exact quote, the same acknowledged reduction in verifiability already documented for visual classification.

## Failure behavior (summary)

- Invalid/unparseable structured extraction output after the same one-retry technical policy as classification → `extraction_status = "unavailable"`, sanitized failure category/reason, and the document's own `ACCEPTED` status/label are untouched.
- A flagged contradiction is not a failure: both fields stay `present`, confidence goes to `0.0`, and the contradiction is shown explicitly.
- `OTHER` and semantic `UNCERTAIN` documents never reach extraction: `extraction_status = "not_applicable"`.
