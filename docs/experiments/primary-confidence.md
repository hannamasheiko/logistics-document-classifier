# Primary classification feasibility — preparation

## Status

Task 1, control-PDF selection and local text-extraction checkpoint. Four representative text-layer controls now cover `BOL`, `POD`, `INVOICE`, and `OTHER`; the earlier official blank forms remain supplemental controls. This is not a representative evaluation set or a completed G1 experiment. No model, endpoint, prompt, evidence schema, routing formula, or threshold has been selected or tested. No model calls or dependency installations were performed.

The user approved working on `main`; separate branches will be considered only on request for specific risky work.

## Locally verified controls

Files are kept in the ignored `experiments/local-control-pdfs/` directory. These are original blank forms published by their respective organizations, not completed shipment documents and not generated synthetic fixtures. Expected labels below describe form purpose under the agreed taxonomy; they are proposed controls pending user review of using blank forms.

| File | Publisher/source | Expected class | Reason | Local verification |
|---|---|---|---|---|
| `union-pacific-bol-blank.pdf` | [Union Pacific supplier BOL](https://www.up.com/content/dam/upcom/supply/documents/Suppliers_blank%20straight-bol.pdf) | `BOL` | Shipment origin/destination, carrier and cargo description, freight terms, and pickup/carrier acknowledgment. No completed delivery event is recorded. | 1 page; 35,666 bytes; 3,114 extracted characters; rendered page visually inspected. |
| `ups-commercial-invoice-blank.pdf` | [UPS commercial invoice form](https://www.ups.com/assets/resources/webcontent/en_US/invoice.pdf) | `OTHER` | Goods valuation and customs/export purpose, despite the Invoice title and freight amount field. Our `INVOICE` class covers transport-service billing. | 1 page; 140,448 bytes; 912 extracted characters including control characters; rendered page visually inspected. |

Extraction used the existing bundled `pypdf`; rendering used bundled `pypdfium2`. No OCR was applied. Extracted-character counts are diagnostics, not a text-quality score. The blank controls cannot validate extraction of real field values, robust classification across layouts, or reliable escalation thresholds.

SHA-256 (provenance only; not application deduplication):

- Union Pacific: `18475ad467267ea9597a9d75a263277f0df22f2fb51c0e302927d12089585ae1`
- UPS: `227e624f55a2744128b91397bfa0d237b6aef788fc28407a35ad59d3fc9840a6`

## Selected text-layer feasibility controls

The user supplied the following local examples and approved the resulting expected classes. Copies remain in the ignored `experiments/local-control-pdfs/` directory. The raw extracted corpus is stored as four UTF-8 JSONL records in ignored `experiments/local-control-text/primary-text-controls.jsonl`; each record preserves page boundaries and includes source filename, expected class, page count, character count, and page text. Payment account, routing, and SWIFT values are replaced with `[REDACTED]` because they are unnecessary for classification.

| File | Expected class | Pages | Extracted characters | Selection reason |
|---|---:|---:|---:|---|
| `bol_3.pdf` | `BOL` | 1 | 3,772 | Completed U.S. Government Bill of Lading with carrier, origin/destination, cargo, weight, and shipment terms. |
| `dhl_pod.pdf` | `POD` | 1 | 580 | Explicit proof/final-status statement with delivered event, date/time, waybill, destination area, and recipient acknowledgment. |
| `US_Inland_Trucking_Invoice_Filled.pdf` | `INVOICE` | 1 | 1,855 | Transport-service billing with load/BOL references, route, linehaul and accessorial charges, balance due, and payment terms. |
| `commercial_invoice.pdf` | `OTHER` | 1 | 2,446 | Goods/commercial invoice with products, quantities, customs/shipment data, and goods value; it is not carrier billing for transport services. |

The extraction is intentionally local and preliminary. It uses the existing bundled `pypdf`, does not select the future production parser, and does not normalize layout beyond trimming page-edge whitespace and masking the payment identifiers above. No OCR, feature analysis, model call, evidence validation, or routing calculation was performed.

## OpenAI structured-output review and approved live-call budget

Official OpenAI documentation was reviewed on 2026-09-16:

- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) documents schema-adherent output through the Responses API `text.format` JSON Schema path and recommends Structured Outputs over JSON mode. The Python SDK also provides `client.responses.parse` with Pydantic, but the concrete experiment contract remains deferred until the next Task 1 step.
- [Responses API reference](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) confirms text/JSON responses, response usage fields, `max_output_tokens`, and the `store` option. The experiment should use `store: false`; no server-side response retrieval is needed.
- [GPT-5.4 Mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) supports the Responses API and Structured Outputs. Its current dated snapshot is `gpt-5.4-mini-2026-03-17`; published text-token prices are $0.75 per million input tokens and $4.50 per million output tokens.
- [GPT-5.6 Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) is the current balanced model tier and also supports the required endpoint/features, but its published token prices are materially higher ($2 input / $12 output per million). It is not required for the initial simple text feasibility unless the cheaper candidate shows a concrete capability blocker.

Approved configuration:

- endpoint: Responses API (`v1/responses`);
- model: dated `gpt-5.4-mini-2026-03-17` for reproducibility;
- structured response: strict JSON Schema via `text.format`; schema details are the next Task 1 decision, not fixed here;
- reasoning effort: `low` initially;
- storage: `store: false`;
- output cap: at most 1,200 tokens per response for the first pass; increase it only after separate review if a response is `incomplete` specifically because of the output limit;
- required calls: one call for each of the four selected controls;
- retry allowance: at most one retry per document, only for a technical, incomplete, refusal, or schema-level failure, so no more than eight calls total;
- spend guardrail: stop before $0.10 estimated experiment spend and report actual input/output/reasoning usage per call.

The $0.10 guardrail is deliberately conservative. At the published GPT-5.4 Mini prices, an upper-bound planning assumption of 4,000 input tokens and 1,200 output tokens for each of eight calls is approximately $0.0672 before any caching. The initial four-call pass is approximately half that bound. This is an approved budget, not evidence of actual usage; no API call has been made.

## Approved diagnostic features and encoded contract

The diagnostic feature set, strict JSON Schema, and experiment prompt are approved for the live feasibility calls. They are designed to test whether structured class-specific evidence is usable; they do not define weights, a score formula, or a routing threshold.

### Observation semantics

Each diagnostic feature has one status:

- `present`: the text contains explicit, semantically relevant evidence for the feature;
- `absent`: the text is sufficiently readable for this feature to be assessed, but supporting evidence is not present;
- `unclear`: extraction quality, missing context, or ambiguous wording prevents a reliable present/absent judgment.

A `present` observation must include one short exact quote from the supplied text. A heading or keyword alone does not establish a completed fact: for example, a blank `DELIVERED ON` field is not a completed delivery event, and a `B/L NO.` reference inside a commercial invoice does not make that document a BOL. Quotes are provenance checks, not proof that the model interpreted them correctly. `absent` and `unclear` do not require invented evidence.

### Class-specific diagnostic features

| Class | Feature ID | What counts as `present` | Main guardrail |
|---|---|---|---|
| `BOL` | `bol_identity` | The document explicitly identifies itself as a bill of lading or equivalent transport document. | A BOL number mentioned as a reference in another document is insufficient. |
| `BOL` | `bol_transport_obligation` | Language records goods being tendered/received by a carrier for transport and delivery to a consignee, or an equivalent shipment contract/receipt function. | Generic shipment wording or a delivery statement alone is insufficient. |
| `BOL` | `bol_shipment_structure` | Operational shipment details jointly identify the transport movement: carrier plus shipper/consignee or origin/destination plus cargo/packages/weight. | One generic address, weight, or tracking number is insufficient. |
| `POD` | `pod_identity` | The document explicitly identifies itself as proof of delivery, delivery receipt, or a statement of final delivery status. | A blank proof/delivery section or generic word `delivery` is insufficient. |
| `POD` | `completed_delivery_event` | A completed delivery is recorded with actual delivery status and a concrete date/time or location. | Labels awaiting completion do not count. |
| `POD` | `recipient_acknowledgement` | A recipient/signatory name, signature, or equivalent completed acknowledgement is recorded. | An empty signature label does not count. |
| `INVOICE` | `transport_invoice_identity` | The document is an invoice whose primary purpose is billing for transport/logistics services by a carrier, broker, or logistics provider. | The word `invoice` alone is insufficient because commercial goods invoices belong to `OTHER`. |
| `INVOICE` | `transport_charge_breakdown` | Charges are for transport services such as linehaul, freight, fuel surcharge, detention, chassis, lumper, or similar service components. | Freight shown only as part of goods valuation is insufficient. |
| `INVOICE` | `payment_obligation` | A payer/bill-to relationship and an amount due, due date, or payment terms establish a request for payment. | Bank details alone are insufficient. |
| `OTHER` | `non_target_identity` | The document explicitly identifies a non-target type, such as a commercial/customs invoice, rather than one of the three target purposes. | Absence of target-class keywords does not establish `OTHER`. |
| `OTHER` | `non_target_primary_purpose` | Positive content shows another primary purpose, such as valuing traded goods through product quantities, HS codes, countries of origin/destination, Incoterms, or customs totals. | Shipment-related details may occur in non-target documents and must be interpreted with the primary purpose. |

### Cross-class diagnostics

The structured response should also expose, rather than hide, these observations:

- `combined_bol_pod`: both a BOL transport function and an actually completed delivery acknowledgement appear to be substantive parts of the same document;
- `multiple_target_purposes`: evidence materially supports more than one target class without a clear primary document purpose;
- `insufficient_readable_content`: the supplied text is too incomplete or damaged for the feature judgments;
- `contradictory_evidence`: the proposed class conflicts with stronger evidence about the document's primary purpose.

These are diagnostic observations, not final backend outcomes. In particular, the already agreed combined BOL/POD rule is applied by routing later; the model does not decide `ACCEPTED`, fallback, or `UNCERTAIN`.

### Minimal structured response shape to test

The live experiment should return:

1. one `candidate_class` from `INVOICE`, `BOL`, `POD`, or `OTHER`;
2. the fixed diagnostic feature statuses above, with a short exact evidence quote only for `present` features;
3. the four cross-class diagnostic statuses;
4. no self-reported probability, acceptance decision, fallback decision, score, or threshold.

The exact JSON Schema and Python representation remain experiment details. They should encode this information compactly enough for the 1,200-token first-pass limit and may be adjusted only for schema/API feasibility without changing the feature meanings silently.

### Encoded experiment contract

- `experiments/primary_confidence.py` contains the strict Responses API `text.format` object named `primary_classification_evidence`, the complete classification instructions, and the helper that delimits document text as untrusted data.
- Every object schema sets `additionalProperties: false` and requires every declared property. Every feature and diagnostic observation requires a `present / absent / unclear` status plus `string | null` evidence.
- The prompt repeats the fixed taxonomy, status semantics, feature meanings, `OTHER` guardrail, known heading/reference traps, and the instruction that the model must not decide score, acceptance, fallback, or `UNCERTAIN`.
- `experiments/tests/test_primary_confidence.py` checks the fixed IDs, strict object closure, status/evidence shape, prompt/schema alignment, and untrusted-data delimiters.
- The schema and prompt were approved before adding the live runner.

### Prepared live runner and credential boundary

The standalone runner is implemented but has not been executed against OpenAI. The bundled workspace Python does not contain the OpenAI SDK, and no package was installed automatically. The proposed isolated experiment environment pins the official Python SDK to `openai==3.14.1`, the current release reviewed on 2026-09-16.

Safeguards in `experiments/primary_confidence.py`:

- live execution requires the explicit `--run-live` flag and the presence of the `OPENAI_API_KEY` environment-variable name;
- the program never receives the key as a command argument and does not read or print its value; the SDK consumes it from the process environment;
- a present `OPENAI_LOG` variable blocks execution to prevent external SDK debug logging;
- SDK automatic retries are disabled; the experiment owns the approved one-retry-per-document rule and eight-call global cap;
- the request timeout is 60 seconds; retryable transport/rate/server errors receive one retry, while configuration errors stop immediately;
- `incomplete` caused by `max_output_tokens` stops the experiment without retry or an automatic limit increase;
- only parsed structured observations, generic failure categories, response IDs, usage, latency, and estimated cost are saved; source text, raw responses, HTTP data, and exception messages are not saved;
- local results are written atomically under ignored `experiments/local-results/`;
- the conservative cost calculation uses all reported input tokens at the full input rate and all output tokens at the output rate. Reasoning tokens are recorded but not added again because they are included in output-token usage.

The local setup commands do not call the API:

```bash
cd /Users/annakornieieva/PycharmProjects/logistics-document-classifier
python3 -m venv .venv
.venv/bin/python -m pip install openai==3.14.1
```

The first live call occurs only when this separately reviewed command is run in the same `zsh` session after the key is entered without shell-history exposure:

```bash
read -s "OPENAI_API_KEY?OpenAI API key: "; export OPENAI_API_KEY; echo
unset OPENAI_LOG
.venv/bin/python -m experiments.primary_confidence --run-live --input-jsonl experiments/local-control-text/primary-text-controls.jsonl --output-json experiments/local-results/primary-confidence.json
```

## First live run — local validation failure

The user ran the approved command locally. The runner made all eight allowed calls: one initial call and one retry for each of the four controls. Every Responses API request returned `completed`; there were no technical errors, refusals, or incomplete responses. Reported estimated spend was $0.030717.

| Control | Expected | Calls | API status | Local outcome |
|---|---:|---:|---|---|
| `bol_3.pdf` | `BOL` | 2 | both `completed` | `invalid_structured_output` |
| `dhl_pod.pdf` | `POD` | 2 | both `completed` | `invalid_structured_output` |
| `US_Inland_Trucking_Invoice_Filled.pdf` | `INVOICE` | 2 | both `completed` | `invalid_structured_output` |
| `commercial_invoice.pdf` | `OTHER` | 2 | both `completed` | `invalid_structured_output` |

This local outcome does not establish that the model selected the wrong classes. The failure boundary is after the API response, in JSON parsing or local evidence validation. Because the initial runner collapsed every such failure into one category and did not retain parsed rejected observations, the exact subtype cannot be recovered from this run. `store: false` also means the old response bodies are not available for later retrieval.

The leading hypothesis is a systematic mismatch in the stricter local semantic checks: at least one evidence value may not have been an exact case-sensitive substring, or an `absent/unclear` observation may have contained non-null evidence. This remains a hypothesis until a diagnostic response is captured; strict schema conformance alone does not prove the prompt-level evidence rules.

### Diagnostic instrumentation prepared

Without changing acceptance behavior, the runner now records a safe validation error code, the affected observation ID, and the parsed rejected structured output in the ignored local result. It still does not save raw HTTP data, exception messages, credentials, or the full source document. A `--only-source` mode permits a diagnostic run on one control, preserving the one-retry maximum. No diagnostic API call has been made.

The proposed diagnostic target is `dhl_pod.pdf`, the shortest and clearest control. It would make one call normally and at most two with its allowed retry. This requires separate user approval because the original eight-call cap has already been consumed.

### Diagnostic result and confirmed root cause

The user approved and ran the single-control diagnostic. Both allowed calls returned `completed`; spend was $0.0070725. Both selected the expected `POD` candidate and supported the three POD features with relevant source text. Both were rejected for the same presentation mismatch: every evidence string included literal outer `"` characters, while the source text contained the cited content without those characters. The first reported failure was therefore `evidence_not_exact_substring` on `bol_shipment_structure`.

Both stored responses pass the complete local structural/evidence validation after removing only one pair of outer ASCII quote characters when, and only when, the inner value is an exact source substring. This bounded normalization is now implemented and covered by tests. The prompt also explicitly tells the model not to add quotation-mark characters around evidence. Other non-exact evidence remains invalid.

The diagnostic also exposed a separate semantic error that normalization deliberately does not hide: both responses marked `bol_shipment_structure` as present based only on `shipment with waybill number 5270614856`. That contradicts the feature guardrail that one tracking/waybill number is insufficient. The candidate remained `POD`, the BOL identity and transport-obligation features remained absent, and all ambiguity/contradiction diagnostics remained absent. This is evidence that deterministic sufficiency must require the class-specific feature combination and that evidence still needs semantic review; a structurally valid response is not automatically semantically correct.

### Approved remaining-control rerun

The user approved testing only the remaining `BOL`, `INVOICE`, and `OTHER` controls: three calls normally and no more than six with one retry per document. The already validated POD diagnostic is not repeated. The cumulative spend before this rerun is $0.0377895.

The runner now accepts repeated `--only-source` options and a `--prior-spend-usd` value. Before each call it reserves the conservative $0.0084 planning bound used for the original budget; it will not start a call if prior spend plus current run spend plus that bound would exceed the cumulative $0.10 guardrail.

Approved command, not yet executed:

```bash
python -m experiments.primary_confidence \
  --run-live \
  --input-jsonl experiments/local-control-text/primary-text-controls.jsonl \
  --output-json experiments/local-results/primary-confidence-remaining.json \
  --only-source bol_3.pdf \
  --only-source US_Inland_Trucking_Invoice_Filled.pdf \
  --only-source commercial_invoice.pdf \
  --prior-spend-usd 0.0377895
```

### Remaining-control rerun results

The user ran the approved three-control command. It used four calls and $0.015702, bringing cumulative estimated spend to $0.0534915. There were no technical, refusal, or incomplete outcomes.

| Control | Expected | Candidate | Calls | Local result |
|---|---:|---:|---:|---|
| `bol_3.pdf` | `BOL` | `BOL` on both attempts | 2 | rejected: non-contiguous evidence containing `...` |
| `US_Inland_Trucking_Invoice_Filled.pdf` | `INVOICE` | `INVOICE` | 1 | passed structural/evidence validation |
| `commercial_invoice.pdf` | `OTHER` | `OTHER` | 1 | passed structural/evidence validation |

Together with the revalidated POD diagnostic, candidate classification is correct on all four simple controls. This is useful feasibility evidence, not an accuracy claim for a representative set.

The BOL failure is narrower than a wrong classification. Both responses selected `BOL` and supported the BOL features, but `bol_transport_obligation` replaced omitted source text with `...`; this is not an exact continuous quote and remains invalid. The second attempt also collapsed a PDF line break to a space in `TRANSPORTATION COMPANY TENDERED TO YRC`. Local audit classified all present evidence as follows:

- POD diagnostic: outer quote characters only; already handled by bounded normalization;
- BOL: exact matches plus one non-contiguous ellipsis quote on both attempts and one whitespace-normalized continuous quote on the second;
- INVOICE and OTHER: all evidence values are exact source substrings.

The run also exposed systematic semantic false positives:

- `bol_shipment_structure` was marked present in POD, INVOICE, and OTHER from generic shipment/route references, despite the feature's guardrail;
- the INVOICE marked `completed_delivery_event` present from a delivery-date field without POD identity or recipient acknowledgement;
- the commercial invoice marked `transport_charge_breakdown` present from goods-valuation freight, and `multiple_target_purposes` present using only its non-target commercial-invoice identity;
- one BOL attempt marked payment and non-target-purpose features present, while its retry did not.

These findings support the agreed warning that exact evidence provenance does not prove semantic correctness. They also show that a simple count of all present features would be misleading. Before deterministic routing is designed, two decisions remain for user review: whether continuous evidence matching may normalize PDF whitespace while continuing to reject ellipses, and whether routing should evaluate candidate-class critical combinations while treating model-supplied cross-class diagnostics as advisory or deriving them from feature combinations in the backend.

## Deterministic sufficiency/routing experiment

The user approved both directions for a local rules experiment, without freezing a production score or threshold:

- continuous source evidence may normalize runs of PDF whitespace; ellipses, paraphrases, and non-contiguous excerpts remain invalid;
- routing evaluates complete critical combinations for the candidate class, derives conflicts from complete combinations, and reports model diagnostics only as advisory metadata.

The provisional critical combinations are:

| Class | Required experiment features |
|---|---|
| `BOL` | `bol_identity`, `bol_transport_obligation`, `bol_shipment_structure` |
| `POD` | `pod_identity`, `completed_delivery_event`, `recipient_acknowledgement` |
| `INVOICE` | `transport_invoice_identity`, `transport_charge_breakdown`, `payment_obligation` |
| `OTHER` | `non_target_identity`, `non_target_primary_purpose`, with no complete target-class combination |

The provisional rule order is: valid evidence provenance first; established complete BOL+POD combination → `UNCERTAIN_NO_FALLBACK`; multiple complete target combinations or candidate contradictions → `ESCALATE`; incomplete candidate combination → `ESCALATE`; otherwise a complete candidate combination → `ACCEPT`. In Iteration 1, an escalation would temporarily end as semantic `UNCERTAIN` because visual fallback is not yet present.

`experiments/deterministic_routing.py` implements these pure experiment rules. The candidate match ratio is only the fraction of required candidate features marked present; it is reported for inspection and is not an accepted confidence formula or threshold.

### Results on the latest stored control response

| Control | Expected / candidate | Provenance | Complete class combinations | Experimental action |
|---|---|---|---|---|
| `dhl_pod.pdf` | `POD` / `POD` | valid after bounded quote normalization | `POD` | `ACCEPT` |
| `bol_3.pdf` | `BOL` / `BOL` | invalid: ellipsis in `bol_transport_obligation` | `BOL` | `ESCALATE` (`invalid_evidence`) |
| `US_Inland_Trucking_Invoice_Filled.pdf` | `INVOICE` / `INVOICE` | valid | `INVOICE` | `ACCEPT` |
| `commercial_invoice.pdf` | `OTHER` / `OTHER` | valid | `OTHER` | `ACCEPT`; incorrect model diagnostic remains advisory |

All four candidate match ratios are `1.0`. Therefore these controls do not justify a numerical routing threshold: the ratio does not distinguish the invalid BOL evidence from the three locally accepted results. The separate provenance gate is material, and the semantic-review findings still show false-positive non-candidate features even in accepted records.

Synthetic rule cases verify that an incomplete candidate combination escalates, a complete BOL+POD combination becomes `UNCERTAIN_NO_FALLBACK`, positive `OTHER` is contradicted by a complete target combination, and model-reported diagnostics do not override deterministic combinations. These are behavior checks for the experiment direction, not evidence that the rules are calibrated or production-ready.

The experiment supports feasibility of evidence-based deterministic routing on the simple controls, with a separate provenance gate and class-combination rules. It does not establish the final score, threshold, feature weights, or routing quality. Those require missing/unclear, ambiguity, contradiction, and representative examples in the later systematic evaluation stage.

## Proposed minimal evidence-based result contract (Task 1, point 8)

This is a logical contract for the next gates, not a frozen Python type or database schema.

1. **Model observation:** candidate class; every fixed class feature and diagnostic with `present / absent / unclear` plus evidence for `present`; model diagnostics retained as advisory observations.
2. **Provenance validation:** overall validity and per-observation validation method/error. The experiment currently distinguishes exact, bounded outer-quote normalization, whitespace-normalized continuous evidence, and invalid evidence.
3. **Derived evaluation:** complete class combinations, candidate match ratio for inspection, and backend-derived ambiguity or contradiction flags. The ratio remains provisional and is not a probability or accepted threshold.
4. **Routing decision:** `ACCEPT`, `ESCALATE`, or `UNCERTAIN_NO_FALLBACK`, with a reason and nullable accepted class. A candidate class is never automatically a final accepted class.
5. **Execution metadata:** provider, endpoint, model and prompt/schema/rules identifiers; response/call count; token use, latency, and estimated cost.
6. **Technical failure:** separate failure stage and sanitized category. It must not be represented as semantic uncertainty or an accepted candidate.

Contract invariants proposed for later application design:

- `accepted_class` exists only for `ACCEPT`;
- invalid evidence provenance cannot produce `ACCEPT`;
- model-reported cross-class diagnostics do not override backend-derived combinations;
- `OTHER` needs its positive non-target combination and no complete target combination;
- any reported score is an explainable routing signal, never a probability of correctness;
- persist normalized observations and sanitized operational metadata, not credentials, raw HTTP payloads, or raw exception text;
- exact field names, Python types, and persistence representation remain decisions for G0/GE;
- runtime processing does not require an independent ground-truth oracle.

### Hypotheses to test in Task 2E

1. The candidate class remains useful across a small representative set; inspect per-class outcomes and confusion rather than aggregate controls alone.
2. Requiring valid provenance and a complete candidate-specific critical combination reduces incorrect acceptance; measure accepted-correct, accepted-incorrect, correct escalation, and unnecessary escalation separately.
3. Exact/normalized continuous matching detects unsupported quotations but cannot establish semantic correctness; manually audit the meaning of accepted evidence.
4. Positive `OTHER` requirements prevent incomplete or unreadable target documents from becoming `OTHER` merely through missing target evidence.
5. Backend-derived complete BOL+POD evidence produces the agreed semantic uncertainty without fallback, while unresolved BOL/POD/combined evidence escalates.
6. The unweighted candidate match ratio may be insufficient. The four current controls all score `1.0`, so incomplete, unclear, ambiguous, and contradictory examples are required before selecting a formula or threshold.
7. Advisory model diagnostics add useful review context but should not determine routing unless later evidence shows a specific backend rule needs revision.

Task 2E should record per-class counts, accepted-correct and accepted-incorrect results, correct and unnecessary escalations, semantic uncertainty, provenance errors, and semantic evidence errors. Task 1 sets no numerical target or working threshold.

## G1 review — approved

**Decision:** G1 was approved for the evidence-based architecture direction and minimal result contract. Production routing settings, a score formula, a threshold, and demonstrated routing quality were not approved and remain deferred to Task 2E.

### Experiment basis and actual usage

- Four user-supplied text-layer controls: one expected `BOL`, `POD`, `INVOICE`, and `OTHER`. They are simple controls used while shaping the prompt and rules, not an independent held-out set. Redistribution permission has not been established.
- OpenAI Responses API; `gpt-5.4-mini-2026-03-17`; strict Structured Outputs; `reasoning=low`; `store=false`; `max_output_tokens=1200`; local SDK `openai==3.14.1`.
- Fourteen calls across the initial run, POD diagnostic, and remaining-control run. Total usage: 40,284 input tokens, 5,173 output tokens including 980 reasoning tokens. Cumulative estimated spend: $0.0534915.
- Recorded total latency: 46.962 seconds; mean 3.354 seconds per call, minimum 2.178 and maximum 5.746. This small diagnostic run is not a performance benchmark.

### Factual result

| Control | Candidate classification | Latest deterministic outcome | Material finding |
|---|---|---|---|
| `dhl_pod.pdf` | expected `POD` | `ACCEPT` | Evidence became valid after bounded removal of literal outer quote characters. |
| `bol_3.pdf` | expected `BOL` on both attempts | `ESCALATE` | Required evidence used an ellipsis/non-contiguous quote and remains invalid. |
| `US_Inland_Trucking_Invoice_Filled.pdf` | expected `INVOICE` | `ACCEPT` | Complete invoice combination with valid source evidence. |
| `commercial_invoice.pdf` | expected `OTHER` | `ACCEPT` | Positive non-target combination; an incorrect model ambiguity diagnostic remains advisory. |

All four candidate classes matched their manually expected labels. The latest routing experiment accepts three controls and escalates the BOL because of provenance. This supports API/schema feasibility and the use of deterministic critical combinations, while also showing that strict structure and exact provenance do not remove semantic feature errors.

### Limitations and unresolved evidence

- Four simple controls cannot establish accuracy, routing reliability, calibration, or a working threshold. They contain no deliberately incomplete, unclear, combined, or contradictory example.
- The controls influenced the prompt and rules and are not held out. `OTHER` is represented only by a commercial invoice.
- Scanned PDFs, OCR, page images, visual fallback, and fallback acceptance are outside Task 1 and untested here.
- The BOL still fails provenance because the model used an ellipsis. The prompt now explicitly prohibits ellipses and non-contiguous quotations, but that post-run wording has not been live-tested.
- Semantic false positives occurred in non-candidate features. A valid quote confirms source provenance only, not the model's interpretation.
- The stored calls span bounded prompt/validator revisions rather than one frozen configuration. Cost and latency are descriptive, not benchmarks.
- No score formula, feature weights, or threshold has been selected. The observed candidate match ratio is `1.0` for every control and therefore has no demonstrated routing discrimination.

### Frozen experiment identifiers

- provider: `openai`
- endpoint: `responses`
- model: `gpt-5.4-mini-2026-03-17`
- config: `primary-text-feasibility-v1`
- prompt: `primary-classification-evidence-v1`
- schema: `primary-classification-evidence-v1`
- routing rules: `critical-combinations-experimental-v1`

G1 approval freezes these experiment identifiers and makes the minimal contract and findings available to G0 and Task 2E. The corrected prompt and routing behavior still require the systematic evaluation specified in Task 2E. No Task 2 work was started as part of closing G1.

### Expected diagnostic behavior on the four controls

- `bol_3.pdf`: the three BOL features should be supported. Delivery-field headings alone must not establish `completed_delivery_event`; layout loss may make that observation `unclear` rather than `absent`.
- `dhl_pod.pdf`: POD identity, completed delivery event, and recipient acknowledgement should be supported by the final-status wording, delivered timestamp, and named signer.
- `US_Inland_Trucking_Invoice_Filled.pdf`: the three transport-invoice features should be supported by the broker invoice identity, transport-service charge lines, and total/payment terms.
- `commercial_invoice.pdf`: positive commercial-goods purpose should support `OTHER`; `B/L NO.` and freight/incoterm content must not be mistaken for a BOL or transport-service invoice.

## Candidates not ready as local control inputs

| Source | Expected use | Why not included in the ready set |
|---|---|---|
| [Old Dominion BOL](https://www.odfl.com/content/dam/odfl/us/en/documents/fill-print-forms/Printable_Bill_of_Lading_BOL.pdf) linked from its official forms page | Alternative blank `BOL` | Web tool exposes one page and form text, but direct download returned HTTP 403. Union Pacific supplies the currently available BOL control. |
| [FedEx POD in Connecticut Siting Council filing](https://portal.ct.gov/-/media/csc/2_ems-medialibrary/westhartford/newbritainav/verizon/emver155181102filingnewbritainavepdf.pdf?hash=555F5EEB2D70B114AE3C0AE190AB6B28&rev=4941cb2916aa457ba4dc404c4e291e3e) | `POD`: a letter on PDF page 27 (1-based) documents delivered status, recipient acknowledgment, delivery date and tracking reference | The 28-page source contains several documents and cannot be submitted intact. A separately extracted, provenance-labelled POD page would be required. Direct download timed out; no local text-layer or visual verification completed. Government-hosted carrier document, not a blank or synthetic sample; not independently authenticated with the carrier. |
| [UPS US Rate and Service Guide, 2003](https://www.ups.com/media/en/service_guide_03_us_daily.pdf) | Reference for a transport-service `INVOICE` | PDF page 148 (printed page 146) embeds illustrative invoices alongside explanatory material. The 163-page guide is not an invoice input; extracting that whole page would retain instructions and overlapping samples. Historical official sample, not a real standalone customer invoice. Excluded from classification controls. |
| [FedEx Custom Critical combined form](https://www.fedex.com/content/dam/fedex/us-united-states/shipping/images/BillofLading.pdf) | Candidate for established BOL/POD ambiguity → `UNCERTAIN`, no fallback | Official blank combined form identified in earlier research. Direct download returned HTML rather than a PDF; not locally verified or included. Do not assume this blank form demonstrates a completed delivery. |

## Source and redistribution boundary

The two blank forms are downloadable from official organizational domains. The four selected filled controls were supplied locally by the user; their redistribution permission and original publication provenance have not been established. Keep all source PDFs and extracted text out of Git and do not claim that they are redistributable. Nothing has been uploaded to an LLM API. This is a provenance/permission-status record, not a legal conclusion.

## Checks, corrections, and next decision

- Confirmed actual PDF signatures before extraction: two FedEx downloads instead contained HTML and were rejected, despite successful HTTP transfer.
- Union Pacific and UPS controls have one page each and are below the agreed size/page limits.
- Poppler rendering encountered Fontconfig errors; existing PDFium rendered both inspected pages successfully. This does not select the production PDF library.
- The user accepted the blank forms as supplemental first-probe controls and supplied filled examples. The selected four-document text-layer subset covers every agreed class once, but it does not establish representative coverage or routing reliability.
- The JSONL corpus was re-read successfully after generation; expected-class order, record count, page counts, and page arrays were checked. Five payment identifiers were masked.

No manifest or tuning/held-out split is created at this step. Across the approved calls, all four controls received the expected candidate class. The local deterministic experiment accepts POD, INVOICE, and OTHER and escalates BOL because of invalid evidence provenance. Candidate ratios are `1.0` for every control, so no numerical threshold or final score is selected. No further API call has been authorized or executed.
