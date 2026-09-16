# AI-assisted engineering history

This is a curated record of meaningful engineering work, not a transcript. The original prompts below are preserved without language editing; an English translation is placed immediately after each one. Short confirmations are summarized in decisions rather than reproduced as separate stages.

## 1. Collaboration rules

Before design began, the user requested a repository-level `AGENTS.md` with rules for decision-making, explicit commit approval, result verification, protecting secrets, and maintaining this record. The assistant created the file, grouped the 15 rules by topic, and read it back for verification. The user approved the instructions and prohibited making a commit for now.

**Original approval (English):**

> I approve `AGENTS.md` as the repository instructions. Do not commit it yet. We can proceed to the next step.

The initial prohibition on creating `AI_WORKFLOW.md` applied only to the instructions-creation step. The current checkpoint was created following the user's subsequent explicit request. Approval of the instructions is not approval of the architecture or implementation.

## 2. Brainstorming — in progress

**Checkpoint:** 2026-09-15. **Status:** unfinished; the final design has not been approved. Planning and implementation have not started. This logical stage has not concluded with a commit.

### 2.1. Original assignment and analysis boundaries

The employer requests a basic Django-based PDF classifier for US logistics documents, with confidence and a switch to a more expensive/visual model when the score is low. Invoice, BOL, and POD are given as examples. Field extraction with confidence is optional. The PDF input channel can be chosen; a repository should preferably be provided upon completion.

The employer did not provide sample PDFs or correct labels. The assistant applied Superpowers Brainstorming; the initial inspection found only `AGENTS.md` among regular files, and `git log` reported that there were no commits.

**Original prompt (translated from Ukrainian):**

> We are starting work on the take-home assignment.
>
> Below I provide the **original assignment text from the employer without changes**:
>
> **Brief description of the assignment:**
> build a basic document classifier for documents of American logistics companies (for example, Invoice, BOL, POD, etc.)
> PDF input (in any form—UI upload, API request, email, etc.), classification with a confidence score. Switch to a more expensive/visual model when the score is low
>
> optionally—extract fields + confidence scores for them
> stack—Django, any OCR/LLM of your choice
>
> when ready, preferably upload it to Git and send a repository link (it can be public, or I can send a username if it will be private)
>
> **Use Superpowers Brainstorming at this stage.**
>
> For now, **do not implement anything, install dependencies, or initialize Django**. I first want to go through a full stage of analysis and solution design together with you.
>
> During brainstorming:
>
> - analyze the assignment requirements and distinguish explicit requirements from assumptions;
> - identify ambiguities and questions that actually affect the design;
> - help define a reasonable scope for the take-home assignment;
> - consider the PDF processing architecture, including text-based and scanned/image PDFs;
> - separately and critically examine the `confidence score`: what exactly it should mean in this system, how it can be obtained, and how reliable it is;
> - separately examine the condition for switching to a more expensive/visual model when the score is low: when such a fallback actually adds value and what new information or capability it provides;
> - identify which document taxonomy decisions (Invoice, BOL, POD, `OTHER`, possible additional types) we need to make;
> - for now, treat optional field extraction as a separate extension after the main classification pipeline;
> - propose alternatives where they are genuinely significant, with trade-offs, but **do not make significant decisions for me**.
>
> Do not try to immediately produce a final architecture and implementation plan. Conduct brainstorming interactively according to the Superpowers workflow: explore the problem, ask me questions when my decision is needed, and gradually develop the design.
>
> We will move to Planning separately, only after I explicitly approve the design.

### 2.2. Taxonomy: limit the first iteration, examine ambiguity

The user chose iterative development: first three types, verification, then expansion. The assistant clarified that BOL in the assignment means Bill of Lading, not the general term “bill.” `OTHER` was approved for understandable documents outside the target types, separately from uncertainty, unreadability, and technical errors. One PDF means one document, possibly spanning multiple pages; segmentation of document bundles is out of scope.

At the user's choice, `INVOICE` was narrowed to invoices for transportation/logistics services. A Commercial Invoice for goods is `OTHER` in the first version.

The assistant initially proposed keeping signed/combined BOLs in the BOL class. The user requested evidence and actual official examples before approving the BOL/POD boundaries.

**Original prompt (translated from Ukrainian):**

> Yes, look, let's use the top five American delivery companies as a basis, for example FedEx, American Express, DPT, UPC, and so on. And look at the list of their documents that they provide as BOL, POD, invoice. And compile a list from them that can be clearly classified. Where you marked documents that have both forms on them, most likely this is a detachable form, where the document is split into two parts: one remains as BOL, the other as POD. So the document in its original form has both these parts, but in practice we should recognize them separately. If you find information that BOL and POD nevertheless remain in one document, then an additional classifier, such as BOL slash POD, needs to be introduced. But that will be later; at the initial stage we must classify documents clearly. Perform this analysis.

**Research and correction:**

- The assistant explicitly chose FedEx/FedEx Freight, UPS, DHL, XPO, and Old Dominion as a working sample in the US market, not as a proven top-five ranking. The companies and divisions cover different types of transportation; their forms are not one universal set.
- XPO and FedEx documentation distinguish BOL, Delivery Receipt/SPOD, and Freight Bill/Invoice. Old Dominion confirms separate BOLs, PODs, and invoices.
- Public official BOL forms, a POD in a government archive, and official invoice materials were found. A complete set of 15 filled-in examples was not obtained. Some customer documents are available only after login.
- The FedEx Custom Critical form has both titles, a shared cargo description, shipping and delivery records, and copy labels for the parties. No instruction to detach one part from the other was found. Physical separation has not been established; a copy of this form completed after delivery was not verified.
- Ultimately, the user approved the following: a combined BOL/POD returns an undetermined result with an explanation; it is not `OTHER`, not a forced BOL/POD choice, and not a new class in the first iteration. The earlier proposal to automatically classify combined forms as BOL was rejected.
- Candidates for future expansion: Rate Confirmation, Lumper/Unloading Receipt, Weight Ticket, Packing List, Air Waybill, Certificate of Origin, Freight Claim. They were not added to the current scope.

**Reference sources:**

- [XPO Document Finder](https://www.xpo.com/help-center/document-finder/)
- [Old Dominion: forms](https://www.odfl.com/us/en/resources/fill-print-forms.html), [FAQ](https://www.odfl.com/us/en/resources/freight-knowledge/old-dominion-faqs.html)
- [FedEx Freight BOL](https://www.fedexfreight.com/content/dam/web/us/documents/uniform-straight-bol.pdf)
- [FedEx Custom Critical BOL/POD](https://www.fedex.com/content/dam/fedex/us-united-states/shipping/images/BillofLading.pdf)
- [FedEx POD at Connecticut Siting Council, pages 4–6](https://portal.ct.gov/-/media/csc/2_ems-medialibrary/fairfield/congressst/sprint/emsprint051171018filingcongressstpdf.pdf?hash=7E87BC50025933C9CBC9EA7DEFE1B8F0&rev=029cdcd94e2d440d871e8b58598e1b33#page=6)
- [FedEx API guide 2021, document types, pages 919–921](https://www.fedex.com/us/developer/downloads/pdfs/2021/FedEx_WebServices_DevelopersGuide_v2021.pdf#page=919)
- [UPS Freight Invoice Instructions](https://dtciportal.ups.com/tools/forms/freight_invoice.pdf) — the search index provided the content; opening it directly with the tool failed.
- [C.H. Robinson: required paperwork](https://www.chrobinson.com/en-us/carriers/carrier-support/support-required-paperwork/)

### 2.3. PDF processing and fallback iterations

**Original prompt (translated from Ukrainian):**

> To start with, I want to do PDFs with a text layer. That is, so we go through this: we have those three classes, and a PDF is submitted as a separate document containing text. Once we develop it, test it, and are confident that everything works, we will then make it more complex by adding scanned PDFs, which are images, too. So I definitely want to include that, but after we go through this first basic layer.

**Agreed direction:**

1. First iteration: text-layer PDF → text extraction → inexpensive text model → classification result.
2. Next mandatory iteration: scanned PDF → OCR → the same text classifier → when needed, a visual model with the original images.
3. Optional field extraction is considered after the main classification pipeline.

The alternative “inexpensive visual → stronger visual” was discussed; the user chose OCR → text → visual fallback. The assistant clarified its earlier simplification: a stronger text model could potentially interpret the same text better, but will not recover information lost during extraction/OCR. Visual fallback can add information from the page, but does not eliminate taxonomy ambiguity or guarantee a correction. Specific models and routing conditions remain open.

### 2.4. Confidence: objection to a premature choice

**Original prompt (translated from Ukrainian):**

> I generally agree with interpreting confidence as an estimate of confidence in the correctness of classification, separate from OCR quality. But I do not yet want to fix the decision that the first working version must use an LLM self-reported score.
>
> Since the assignment requires low confidence to trigger fallback to a more expensive/visual model, this score will affect system routing rather than being only an informational field.
>
> Therefore, before choosing an approach, I want to examine separately:
>
> - which confidence signals are actually available for the models/APIs we can use for classification;
> - whether we can obtain a more objective signal than simply asking an LLM to generate a number from `0–1`—for example, model probabilities/logprobs, if the chosen API/model supports them;
> - which practical alternatives to self-reported confidence make sense specifically for a small take-home without building a separate ML system;
> - how a confidence/routing signal can be checked on a small labeled evaluation set;
> - and only then choose a specific confidence implementation for the first version.
>
> We can keep self-reported LLM confidence as one candidate or V0, but I do not yet want to automatically make it the final routing signal.

The assistant acknowledged that recommending a self-reported score had been premature. Logprobs, self-report, consistency of repeated responses, feature checks, and a second LLM verifier were examined. None was approved as the final formula.

Logprob describes the probability of an output token given a particular context, not automatically the probability that a class is correct. Short class codes, the need to check tokenization, incomplete top-logprobs, the unsuitability of averaging the entire JSON, and the distinction between a ranking signal and calibration were discussed. OpenAI Docs was used to check the documentation. No actual model calls were made.

**Original prompt (translated from Ukrainian):**

> The PI provider has effectively already been chosen: **OpenAI API**. I already have practical experience with it, configured access and billing, so I want to use it by default for this take-home.
>
> Another provider should be considered only if, during design, it turns out to offer a substantial technical advantage over OpenAI for a specific important requirement of this assignment. I do not want to add multi-provider research without a concrete need.
>
> Also take the scope constraint into account: this is a take-home assignment with approximately **2–3 days of available development time**. Therefore, the solution must be technically justified and demonstrate the key assignment requirements without turning the work into a production-scale ML/calibration research project.
>
> For confidence, record the following for now:
>
> - we do not consider self-reported LLM confidence a calibrated probability of correctness;
> - logprobs in the OpenAI API look like a potentially more useful routing signal and should be tested in practice for the specific chosen model/endpoint;
> - confidence in our system is primarily needed for the `accept classification vs fallback` decision, not for a claim of statistically precise probability;
> - we are not requiring a dataset of 60–100 documents or a full calibration study;
> - instead, we will provide a small representative evaluation set, realistic for a take-home, to check classification and routing/fallback behavior;
> - we are not fixing a specific threshold or the final confidence calculation method without practical verification.

**Agreed:** OpenAI by default, a 2–3-day budget, and a small evaluation set without an approved size. The assistant's proposal of 60–100 documents was not accepted as a requirement. Logprobs are a candidate; self-report is not the final decision. The score is not OCR quality.

**Verification ideas, not yet a final protocol:** compare classification errors, the proportion of accepted results, errors among accepted results, the proportion of errors routed to fallback, and corrections/degradations after fallback. Do not tune the threshold on final test examples; avoid leakage of identical templates. If there are too few errors, do not claim proven routing reliability.

**Sources:** [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create), [OpenAI Responses](https://developers.openai.com/api/reference/cli/resources/responses/methods/create), [Guo et al., calibration](https://proceedings.mlr.press/v70/guo17a.html). Parameters being present in the documentation does not replace checking the chosen model/endpoint.

### 2.5. UI and persistence: from a one-time response to minimal history

The user chose a PDF upload web interface with a classification button and a result: type, score, and fallback information. An API-endpoint-only option was not chosen.

The assistant proposed processing without persistence. The user objected to automatic simplification and requested a use-case assessment with optional extraction. A one-time result/JSON, results-only history, and history with the original PDF were discussed. Field extraction itself does not require persistence; returning to the result and checking it against the original give persistence concrete value.

**Original prompt (translated from Ukrainian):**

> I choose persistence, but want to keep it minimal and proportional to the take-home scope.
> I see the main scenario as follows: the user uploads a PDF → the system processes it → shows the classification result and, if we implement optional extraction, extracted fields → the result is saved so it can be revisited together with the original document.
> So for now, I see value in storing document metadata, the original PDF, the classification result and confidence, information about the model/fallback used, and extracted fields and their confidence if we implement extraction.
> For persistent relational data, I lean toward **PostgreSQL**, since I already work well with it and using it does not create significant additional implementation overhead for me. But before fixing this decision, assess whether PostgreSQL provides sufficient practical value in this project compared with SQLite, taking into account how easily a reviewer can run the project.
> The PDFs themselves can be stored through Django local media storage unless a reason for a more complex solution emerges during brainstorming.
> I do not want to turn persistence into a full user cabinet: no authentication, user accounts, external object storage, or additional infrastructure without a separate need.
> An upload flow, result page, and minimal history/list view are enough.
> Continue brainstorming.

**Alternatives and decisions:** SQLite is sufficient for the current data and easier to start; PostgreSQL is not required merely because of JSON fields. The user's argument is practical experience and low overhead for them. The assistant proposed PostgreSQL as the only database with minimal Docker Compose for the database to simplify reproducible startup by a reviewer; the user agreed. Supporting two databases is not part of the agreed direction. Compose for the entire application was not approved.

**Agreed data to store:** metadata, original PDF, classification/confidence, model/fallback information; extracted fields/confidence only if optional extraction is implemented. PDFs use local media; relational data uses PostgreSQL. The exact data model has not yet been designed. The assistant's suggestions about error statuses and detailed attempt records should not be considered an approved schema.

**Comparison sources:** [Django JSONField](https://docs.djangoproject.com/en/5.2/ref/models/fields/#jsonfield), [Django FileField](https://docs.djangoproject.com/en/5.2/ref/models/fields/#filefield), [Django databases](https://docs.djangoproject.com/en/5.2/ref/databases/), [SQLite: appropriate uses](https://www.sqlite.org/whentouse.html).

## 3. Summary of accepted decisions

| Area | Agreed |
|---|---|
| Process | Interactive Brainstorming; final design and Planning require separate approval |
| Time | Approximately 2–3 days of development |
| Stack | Django, OpenAI API by default |
| Input | One PDF means one document; text layer first; scans in the next mandatory iteration |
| Classes | INVOICE for logistics services, BOL, POD, OTHER |
| Ambiguity | Combined BOL/POD returns an undetermined result with an explanation, without a new class |
| Future scans | OCR → text classification → visual fallback when needed |
| Confidence | Routing signal, separate from OCR quality; test logprobs; formula/threshold remain open |
| Evaluation | Small representative set; no mandatory 60–100 examples or calibration study |
| UI | Upload flow, result page, minimal history/list view |
| Persistence | Metadata, PDF, classification/confidence, model/fallback; optional extracted fields/confidence |
| Storage | PostgreSQL, minimal Compose for the database, Django local media for PDFs |
| Outside current scope | Authentication/accounts, external object storage, PDF segmentation, additional classes |
| Optional | Field extraction after the main pipeline; fields and confidence mechanism not yet chosen |

## 4. Open questions — not accepted decisions

- **Last question before the checkpoint:** the assistant proposed synchronous processing in an HTTP request instead of a background worker/queue. The user has not answered yet. Synchronous processing is not approved.
- Specific OpenAI models/endpoints; practical support for logprobs and the response format.
- Confidence formula, threshold, fallback start/stop conditions, behavior when fallback is uncertain.
- Specific PDF extraction/OCR tools, size/page limits, and processing time limits.
- Composition and size of the evaluation set, sources of suitable documents, quality acceptance criteria.
- Exact data schema, statuses, how attempts/fallback are stored, repeated upload and deletion behavior.
- Reviewer quickstart details, starting Django, deployment (not requested), UI presentation.
- Whether there will be time for optional extraction; which fields and reliability assessments are needed.
- The final design and implementation plan have not been prepared or approved.

## 5. Work performed, verification, and checkpoint boundaries

- Before the checkpoint, only `AGENTS.md` had been created; in this step, `AI_WORKFLOW.md` was created at the user's explicit request.
- Read-only context inspection and web research of official sources were performed. Conclusions from documentation are not results of testing the application or model APIs.
- Django has not been initialized, dependencies have not been installed, and application code has not been implemented. Model APIs were not called; secrets were not read.
- The documentation was checked for structure, matching originals/translations, and separation of accepted decisions from open questions. Application tests were not run: there is no implementation.
- This file is an intermediate checkpoint, not the completion of Brainstorming. The next brainstorming question awaits the user's review of the checkpoint.

## 6. Request for this checkpoint

**Original prompt (translated from Ukrainian):**

> Before we continue brainstorming, I want to record the current intermediate result in `AI_WORKFLOW.md`.
>
> Do not finish Brainstorming or move to Planning or implementation. This is only a documentation checkpoint.
>
> Create `AI_WORKFLOW.md` according to the rules in `AGENTS.md` and record the project's current meaningful engineering history based on our actual conversation in this thread.
>
> For the current stage:
>
> - preserve my meaningful original prompts in Ukrainian and add an English translation alongside them;
> - do not turn the file into a raw transcript or include every short message;
> - record important questions, alternatives, my clarifications/objections, and the decisions we have reached;
> - clearly separate decisions already accepted from questions that remain open;
> - do not invent reasoning or decisions that did not occur in our conversation;
> - mark the current brainstorming stage as unfinished / in progress;
> - do not add a commit yet, since this logical stage is still ongoing.
>
> After creating it, show me the structure of `AI_WORKFLOW.md` and briefly say which parts of our conversation you included and which you deliberately omitted. Do not proceed with the next brainstorming question until I have reviewed this checkpoint.

## 7. Documentation split and continuation of Brainstorming

**Period:** 2026-09-15–2026-09-16. The earlier checkpoint remains a historical record of the state at that time. The user subsequently requested two content-equivalent language versions: `AI_WORKFLOW.md` in English and `AI_WORKFLOW_UA.md` in Ukrainian. The existing engineering history was split by language without changing its decisions or chronology.

Brainstorming then resumed from the last unanswered question. The following high-level decisions were completed:

- Processing remains synchronous for the take-home. A worker/queue is not introduced; a larger execution model will be reconsidered only if actual limits require it.
- One PDF is one document, with limits of 10 pages and 10 MB. The system does not silently process only part of an oversized document.
- Every accepted upload creates a new processing attempt, including repeat uploads and retries after failure. No file-hash deduplication or result cache is added because reuse would require model/prompt/pipeline versioning and cache invalidation.
- There is at most one classification fallback per attempt. A successful fallback can become the final classification; an unreliable fallback ends as semantic `UNCERTAIN`. A fallback technical error remains a technical failure, and an available primary result is retained only for diagnostics.
- A reliably identified combined BOL/POD is an established taxonomy ambiguity and becomes `UNCERTAIN` without fallback. Uncertainty over whether the document is BOL, POD, or combined is classification uncertainty and can trigger the single fallback.
- Iteration 1 is a text-layer working vertical slice without fallback. Iteration 2 adds scanned PDFs through OCR and one shared visual fallback for both scanned and text-layer inputs. A separate stronger-text fallback is not planned.
- Field extraction moved from a possible stretch goal into planned delivery after the core classifier is stable. Classification retains implementation priority, and removing extraction is only a contingency if a real time or core-pipeline problem occurs.
- Completion criteria cover classification, routing/fallback, semantic ambiguity, technical failures, extraction checked against known expected values, the upload/result/history flow, and reproducible reviewer startup. Runtime extraction is not expected to possess an independent ground-truth oracle.

The proposed feature-based classification idea was recorded as a candidate during Brainstorming: the model could return `present / absent / unclear` class-specific evidence and the backend could calculate a rule-based match score. At that point, the user explicitly deferred feature tables, weights, formula, and threshold until the overall high-level design was complete.

### 7.1. Brainstorming completion and design approval

After the remaining mandatory decisions were closed, a separate design document was created at `docs/superpowers/specs/2026-09-16-document-classifier-design.md`. It records architecture, processing flows, responsibilities, scope, deferred decisions, and trade-offs. It is distinct from this engineering history.

**Original prompt (translated from Ukrainian):**

> I think the structure of this final brainstorming design document is suitable. Create a separate document following it and describe there what we have already approved, clarified, and discussed during this brainstorming. Do not remove anything or add anything on your own that was not discussed and agreed. Do not move to Planning yet.

The user reviewed and approved the design, declared Brainstorming complete, and explicitly authorized the transition to Planning.

**Original prompt (translated from Ukrainian):**

> I reviewed and approve the design document. We consider Brainstorming complete at this point. Move to Planning and prepare an implementation plan based on the approved design, preserving the iterative approach: from the first working vertical slice to the full planned delivery. Include in the plan the points where an experiment or a deferred technical decision is required before implementation. After creating the plan, do not begin implementation—I want to review it first.

## 8. Planning — implementation order and risk reduction

The initial implementation plan placed the full Django intake/persistence foundation before the primary AI experiment. The user challenged that order because the model/API/evidence path is the highest-risk part and can be checked without committing to application schema. The plan was corrected so a standalone feasibility experiment precedes Django models, PostgreSQL, and persistence.

The user then distinguished a small feasibility probe from formal evaluation. The corrected sequence is:

1. **Task 1 / G1 — initial AI feasibility:** a few control text-layer PDFs with known expected results; verify OpenAI structured output, class-specific evidence, and whether deterministic routing is plausible. No manifest, tuning/held-out split, production schema, or working threshold is required.
2. **Task 2 / G0 — application foundation:** after G1, choose versions, the production PDF parser, the minimal persistence representation, and intake semantics. This task does not wait for final routing settings.
3. **Task 2E / GE — systematic primary evaluation:** create the small representative manifest and tuning/held-out classification split, refine evidence rules and the routing score, and choose an initial working threshold. It can proceed alongside the foundation after G1, but Task 3 does not integrate routing until GE is reviewed.
4. **Tasks 3–4 — Iteration 1:** implement and verify the text-layer classifier, routing, persistence, upload/result/history UI, and original-PDF access.
5. **Tasks 5–6 — Iteration 2:** add OCR and the shared visual fallback, then verify the complete classification flow.
6. **Tasks 7–8 — planned extraction:** agree on a narrow extraction contract and implement it without creating a second broad AI research project.
7. **Task 9 / G4 — delivery review:** run the final evaluation and reproducibility checks and report actual limitations.

**Original prompt (translated from Ukrainian):**

> Would it not be better to separate the initial AI feasibility experiment and formal preparation of the evaluation set? For the first experiment, it seems to me that a few control documents with expected results are enough, while the manifest, tuning/held-out split, and more systematic evaluation can be prepared after we verify the model/API/confidence candidates. How do you see it?

The user approved this separation. The feasibility documents are not treated as independent held-out examples later, and a small evaluation set is not used to claim calibration or general statistical reliability.

## 9. Planning — architecture and scope corrections

### 9.1. Application, services, and AI boundaries

The first plan used a flat `documents/` package containing Django views/models, PDF/OCR functions, routing, pipeline orchestration, and OpenAI logic. The user requested clearer responsibility boundaries without introducing multiple Django apps or excessive abstraction.

The accepted structure keeps one Django app and separates:

- the Django application layer at the app root for models, forms, views, URLs, templates, and migrations;
- `documents/services/` for PDF/OCR processing, deterministic routing, orchestration, and persistence lifecycle;
- `documents/ai/` for OpenAI calls, prompts, structured-response validation, classification, and extraction.

Services may use the Django ORM directly. No repository pattern, domain framework, provider framework, worker system, or additional Django apps are added. Concrete dataclasses, shared types, function signatures, and test snippets were removed from the plan because the minimal AI contract must first come from G1 and GE.

**Original prompt (translated from Ukrainian):**

> I still have a question about this part of the plan: I do not really like the proposed flat `documents/` structure, where Django views/models, PDF/OCR processing, routing, pipeline, and AI/LLM logic sit next to one another. Would it not be better to logically separate at least the Django application layer, processing/services, and AI layer without overcomplicating a small project? At the same time, I would not fix specific dataclasses/function signatures before the feasibility experiment, because the minimal AI contract should be one of its results. How would you revise this structure?

### 9.2. Evidence-based confidence/routing selected

The user reconsidered the earlier confidence investigation and proposed one primary architecture: the LLM receives extracted/OCR text and returns a candidate class with structured class-specific features/evidence; the backend deterministically evaluates evidence sufficiency and contradictions and calculates the routing score. Sufficient evidence is accepted; insufficient or contradictory evidence escalates to the single visual fallback in the complete flow. The score is explicitly not a probability of correctness.

This approach was accepted as technically sufficient for the assignment requirement “classification with confidence score + expensive/visual fallback at low score.” Mandatory investigation of logprobs, self-reported confidence, and parallel confidence mechanisms was removed. Alternatives are reconsidered only if the evidence-based approach reveals a concrete blocker.

The retained limitations are:

- deterministic calculation does not make LLM evidence automatically true;
- text evidence quotes are checked against the input text, but a matching quote does not prove correct semantic interpretation or correct OCR;
- features must discriminate classes rather than reward generic field presence, and important contradictions cannot be hidden by a high total score;
- absence of target-class evidence does not automatically establish `OTHER`;
- visual fallback receives original page images, returns structured visual evidence, and passes its own checks; primary thresholds and text-quote checks are not copied automatically.

**Original prompt (translated from Ukrainian):**

> I want to return to the concept of confidence itself, because the current plan with investigation of logprobs and several confidence candidates seems overcomplicated to me.
> I now see a possible pipeline approximately like this: we define characteristic/critical document features for each class; the LLM receives the text after PDF extraction/OCR and returns a structured classification together with the class-specific evidence/features it found; the backend then deterministically evaluates whether this evidence is sufficient and calculates the routing/confidence score. If the evidence is sufficient, we accept the classification; if it is insufficient or contradictory, we go to the visual fallback, after which we obtain the final class or `UNCERTAIN`. We do not call the score a probability of correctness—its usefulness and threshold are checked on a small labeled evaluation set with known correct classes.
> Is this concept technically correct for our task and sufficient for the requirement `classification with confidence score + expensive/visual fallback at low score`? If so, can we make it the main architecture and remove the investigation of several alternative confidence mechanisms? If not, explain specifically where the problem is in this pipeline and what it lacks.

The implementation plan and then the approved design document were synchronized to this evidence-based direction. The design no longer presents confidence mechanisms as parallel candidates. Exact features, deterministic rules, score formula, and thresholds remain outcomes of bounded feasibility/evaluation, not assumptions fixed in documentation.

### 9.3. Field extraction reduced to a narrow planned capability

Task 7 initially resembled a second AI subsystem with its own broad investigation of confidence, model choice, input/call strategy, and validation. The user requested a proportional take-home implementation.

Task 7 is now a short extraction contract and validation checkpoint:

- a small class-specific field schema for `INVOICE`, `BOL`, and `POD`;
- structured `value / status / evidence` results;
- deterministic validators only where meaningful;
- one simple explainable field-confidence calculation based on status, evidence, validation, and contradictions;
- several manually prepared examples with known expected values, including missing/unclear and semantic-error cases;
- a clear rule that extraction errors do not change an already accepted classification.

There is no separate extraction model comparison, confidence-mechanism comparison, input-strategy research, calibration study, or extraction tuning/held-out split. Task 8 implements the agreed contract and verifies it against the expected examples.

**Original prompt (translated from Ukrainian):**

> I still have doubts about the scale of Task 7. Field extraction is part of planned delivery, but right now it looks almost like a second separate AI system with its own experiment around confidence, input/call strategy, validation, and so on. Can we make it simpler for the take-home: a small class-specific set of fields, structured extraction with evidence, deterministic validation where possible, and a simple explainable field-confidence approach—without a separate broad investigation of several mechanisms? Assess what is actually necessary from the current Task 7 and what can be simplified without losing solution quality.

### 9.4. Final scope sanity check and three reductions

A final review concluded that the complete planned delivery is realistic for approximately three focused days, but not a comfortable two-day implementation. No key assignment capability was missing. Three activities with little reviewer-visible value were removed or reduced:

1. Task 5 selects one common local OCR/render stack and runs a smoke test. An alternative is considered only for a concrete blocker; mandatory comparison of OCR libraries was removed.
2. Task 2/G0 does not design deletion UI or a retention policy. Accepted PDFs remain in local media; rejected uploads and temporary processing files are cleaned up.
3. Task 9 manually checks one text-layer case, one scanned/visual-fallback case, and reopening result/history with the original PDF and extracted fields. Uncertainty, technical failures, duplicates, and invalid limits remain covered by automated tests instead of a duplicated full browser matrix.

The evaluation command, small classification held-out set, PostgreSQL with minimal Compose, local media, history, visual-fallback experiment, and short G3 checkpoint were retained because they provide direct reviewer value or implement agreed requirements.

**Original prompt (translated from Ukrainian):**

> After making the last correction, perform a final sanity check of the entire implementation plan. Do not propose a new architecture or expand the scope. Check only whether the plan realistically fits the 2–3 day budget, whether it contains unnecessary formalities/infrastructure/experiments that do not provide noticeable value to the reviewer, and whether any key capability from the assignment has been lost. If you see something that can be safely simplified or removed, name exactly what and why. If the plan is already balanced, say so.

The user approved exactly these three reductions and requested no other plan changes.

## 10. Current state, verification, and commit status

- Brainstorming is complete; the design document is approved and synchronized with the current evidence-based confidence/routing architecture.
- Planning is still under user review. The current implementation plan is `docs/superpowers/plans/2026-09-16-document-classifier-implementation-plan.md`.
- The plan preserves all core assignment capabilities: Django PDF upload, `INVOICE`/`BOL`/`POD`/`OTHER`, classification score, low-score visual fallback, scanned PDFs through OCR, semantic uncertainty, technical failures, minimal persistence/history, and planned field extraction with confidence.
- Planning edits were checked through targeted diffs/searches, task ordering, stale-reference searches, and Markdown fence checks. No application behavior has been claimed as verified.
- Django has not been initialized, dependencies have not been installed, application code and tests have not been created, OpenAI API calls have not been made, and secrets have not been read.
- This documentation stage is recorded in the initial commit `Add initial project design and implementation plan`. Authorization to commit and push this documentation does not start application implementation.

## 11. Task 1 — control-PDF selection in progress

The initial documentation commit `a41f05f` was pushed to `origin/main`. The user subsequently requested step-by-step execution, approved working directly on `main`, and authorized only control-PDF selection at this step.

**Original prompt (translated from Ukrainian):**

> Good, then let's move to the second item—select a control PDF and everything described there.

Two official blank forms were downloaded and inspected: Union Pacific BOL (proposed `BOL`) and UPS commercial goods invoice (proposed `OTHER`). Both are one-page PDFs with extractable text; PDFium rendering confirmed their layouts. The UPS text contains control characters. The files are kept in an ignored local directory because redistribution permission has not been established.

Other sources were assessed: a government-hosted FedEx POD occurs inside a multi-document filing, an official UPS invoice sample is embedded in a guide, and several direct downloads failed or returned HTML. These are not recorded as ready standalone inputs. Poppler hit Fontconfig errors; existing PDFium provided the visual check without installing dependencies.

Details, URLs, hashes, limitations and proposed labels are recorded in `docs/experiments/primary-confidence.md`. The control set is partial; completed INVOICE/POD inputs remain missing and blank-form use awaits user review. No model/API experiment, manifest, application implementation, or new commit was performed. `git diff --check` passed and both downloaded PDFs were confirmed ignored by Git.

## 12. Task 1 — local text-extraction checkpoint

The user accepted the previously found blank forms as supplemental first-probe controls and supplied additional filled BOL, POD, transport-invoice, and unrelated-document examples. The reviewed set was narrowed to one clear text-layer example per agreed class for the initial feasibility probe:

- `bol_3.pdf` → `BOL`;
- `dhl_pod.pdf` → `POD`;
- `US_Inland_Trucking_Invoice_Filled.pdf` → `INVOICE`;
- `commercial_invoice.pdf` → `OTHER` because it bills for goods rather than transport services.

Image-only examples remain reserved for the later OCR/visual iteration. Multi-document PDFs are not submitted intact; any useful page must be separated into its own PDF before use. The selected feasibility controls are not a formal evaluation manifest or independent held-out set.

**Original prompt (translated from Ukrainian):**

> Let us continue Task 1. First prepare local text extraction for the selected text-layer PDFs and save the extracted text in a compact format for later comparison. Do not analyze features yet and do not call the OpenAI API. After extraction, show which documents were read successfully and what text was obtained.

A small standalone extraction utility was added using the already available `pypdf`. It preserves page boundaries and writes compact UTF-8 JSONL containing the source filename, expected class, page count, character count, and extracted text. Four local copies and the generated corpus remain ignored by Git because source provenance and redistribution permission are not established. Payment account, routing, and SWIFT values are masked because they are not needed for classification.

The extraction succeeded for all four controls: `BOL` 3,772 characters, `POD` 580, `INVOICE` 1,855, and `OTHER` 2,446. The generated corpus was parsed back successfully and its record order, labels, page counts, and page arrays were checked. A test-first cycle verified two-page extraction, Unicode JSONL serialization, and payment-identifier masking; all three tests passed. No OCR, feature analysis, OpenAI API call, prompt design, routing calculation, Django work, dependency installation, or commit was performed.

## 13. Task 1 — OpenAI structured-output review and proposed live-call budget

The user closed the control-selection and local-extraction checkpoint and asked to proceed to the next Task 1 item.

**Original prompt (translated from Ukrainian):**

> I consider the second item of Task 1 closed. Move to the next item in the plan.

Official OpenAI documentation was reviewed before any API call. The Responses API supports strict Structured Outputs through `text.format`; the Python SDK also supports parsing structured responses into Pydantic models. Responses expose usage data and support both an output-token limit and `store: false`. The reviewed model pages confirm that GPT-5.4 Mini and GPT-5.6 Terra support the Responses API and Structured Outputs.

For the bounded text-layer feasibility experiment, the proposed starting configuration is the dated `gpt-5.4-mini-2026-03-17` snapshot through the Responses API, strict JSON Schema, low reasoning effort, `store: false`, and a 1,200-token output cap. GPT-5.6 Terra is retained only as a response to a concrete capability blocker because its published token prices are materially higher.

The proposed live-call budget is four required calls, one per selected class control, with at most one retry per document only for a technical, incomplete, refusal, or schema-level failure. This caps the experiment at eight calls. A conservative upper-bound estimate using 4,000 input and 1,200 output tokens per call is $0.0672 at the published GPT-5.4 Mini prices, so the proposed spend guardrail is $0.10. Actual usage must be recorded per call.

The model/configuration and live-call budget remain pending user approval. No API request has been sent, and the feature/evidence schema, prompt, deterministic routing rules, score formula, and threshold have not been designed or selected at this checkpoint.

## 14. Task 1 — approved API budget and candidate diagnostic evidence contract

The user approved `gpt-5.4-mini-2026-03-17`, the Responses API, strict Structured Outputs, low reasoning effort, `store: false`, no more than eight calls, and a $0.10 spend guardrail. The initial `max_output_tokens=1200` remains in place; it will be reconsidered separately only if a response is `incomplete` specifically because of that limit.

**Original prompt (translated from Ukrainian):**

> Yes, I approve `gpt-5.4-mini-2026-03-17`, Responses API, strict Structured Outputs, `reasoning=low`, `store=false`, a maximum of 8 calls, and a $0.10 spend guardrail. We keep `max_output_tokens=1200` for the first test; if we receive `incomplete` specifically because of the output limit, we will then increase it separately. Move to the next item of Task 1.

The next Task 1 item was limited to a compact, reviewable diagnostic feature/evidence proposal. The masked extracted text of the four controls was examined locally. It exposed two useful traps for the feasibility test: the BOL contains uncompleted delivery-field headings, while the commercial invoice contains a B/L reference. Therefore, keywords and headings alone are explicitly insufficient evidence.

The proposal defines `present / absent / unclear` semantics and short exact quotes for `present` observations. It uses three diagnostic features for each target class, two positive `OTHER` features, and four cross-class observations covering combined BOL/POD, multiple target purposes, unreadable content, and contradictory evidence. `OTHER` requires positive evidence of a non-target identity or primary purpose; it cannot be inferred merely from missing target features.

The model should return a candidate class and structured observations only. It must not return a probability, acceptance/fallback decision, deterministic score, or threshold. Exact JSON Schema/Python representation, weights, score calculation, and threshold are still deliberately unset. The feature proposal is pending user review, and no OpenAI API call has been made.

## 15. Task 1 — encoded strict schema and prompt awaiting review

The user approved the diagnostic feature set and authorized encoding the strict JSON Schema and experiment prompt, with an explicit review gate before the first live API call.

**Original prompt (translated from Ukrainian):**

> I approve this feature set. Encode the strict JSON Schema and prompt for the experiment, but show them to me for review before the first live API call.

A standalone `experiments.primary_confidence` module now contains the Responses API `text.format` contract and classification instructions. The schema requires one candidate class, all eleven fixed class-specific feature observations, and all four cross-class diagnostics. Every observation has a required `present / absent / unclear` status and nullable evidence. All object schemas reject undeclared properties.

The prompt defines the four-class taxonomy, treats the document as untrusted data, requires short exact quotes only for present observations, and repeats the agreed guardrails for blank delivery/signature headings, referenced B/L numbers, commercial invoices, and positive evidence for `OTHER`. It explicitly prohibits model-generated probability, score, threshold, acceptance, fallback, or `UNCERTAIN` decisions.

The implementation followed a red-green test cycle. Four new contract tests first failed because the module did not exist, then passed after the minimal implementation was added. No OpenAI SDK import, credential access, API client, or network-call path was introduced. The encoded schema and prompt are awaiting user review before any live call.

## 16. Task 1 — guarded live experiment runner prepared

The user approved the schema and prompt and selected `OPENAI_API_KEY` in the process environment for the standalone experiment. The user required the runner to be prepared with the agreed safeguards and requested an explicit stop with the exact command before the first live call.

**Original prompt (translated from Ukrainian):**

> I approve this schema and prompt for the first live API experiment. We use `OPENAI_API_KEY` through an environment variable for the standalone experiment. Prepare the experiment with these safeguards, but stop before the first live API call and tell me the exact command to run.

The standalone module now includes the approved request configuration, strict response validation, evidence-substring checks, usage/cost accounting, one explicit retry per document, an eight-call global cap, and a $0.10 spend guardrail. An `incomplete` response caused by the 1,200-token output limit stops without retry or automatic limit changes. SDK automatic retries are disabled, and the request timeout is 60 seconds.

Live execution requires `--run-live`, the presence of the `OPENAI_API_KEY` environment-variable name, and the absence of `OPENAI_LOG`. The key is not accepted through command arguments, read by experiment logic, printed, or persisted; the OpenAI SDK consumes it directly from the environment. Results contain parsed observations and operational metadata only. Raw document text, HTTP data, raw responses, exception messages, and credential values are not saved. Local results are ignored by Git.

The bundled Python did not contain the OpenAI SDK. Nothing was installed automatically. The documented local setup uses an isolated `.venv` and pins the current official SDK release `openai==3.14.1`. The live command is separated from setup and requires the user to enter the key without shell-history exposure.

The runner was developed through additional red-green cycles for configuration guards, structured-output validation, orchestration, retry limits, output-limit stopping, safe SDK-response normalization, and generic exception classification. No live API call was made.

## 17. Task 1 — first live run and validation-boundary diagnosis

The user ran the approved four-control experiment locally and supplied the terminal result.

**Original prompt (terminal output):**

> `Experiment finished: 0/4 completed, 8 calls, estimated spend $0.030717.`
> `Sanitized local result: experiments/local-results/primary-confidence.json`

The sanitized result showed that all eight Responses API calls completed: each of the four controls received its initial call and one retry. There were no technical failures, refusals, or output-limit incomplete responses. Every response was rejected afterward by the local JSON/evidence validation under the generic category `invalid_structured_output`.

This does not yet show that model classification failed. The old runner discarded the exact validation subtype and parsed rejected observations, and `store: false` prevents retrieval of the old response bodies. The exact root cause therefore cannot be reconstructed from the first run. The leading hypothesis is a systematic mismatch in strict local evidence checks, such as a non-exact evidence quote or non-null evidence for an absent/unclear observation, but this remains unconfirmed.

The diagnostic gap was corrected without weakening acceptance rules. Test-first changes add safe validation codes, affected observation IDs, and locally stored parsed rejected output while continuing to exclude source text, raw HTTP data, exception messages, and credentials. A single-control `--only-source` diagnostic mode was also added so the whole four-control run does not need to be repeated. The proposed `dhl_pod.pdf` diagnostic uses one call normally and no more than two with retry. No additional call was made because the approved eight-call cap was already exhausted.

## 18. Task 1 — diagnostic run confirms presentation mismatch

The user approved at most two additional calls and ran the single-control `dhl_pod.pdf` diagnostic. It used both calls and reported $0.0070725 estimated spend. Both API responses completed and selected `POD`, but local validation rejected them with `evidence_not_exact_substring` at `bol_shipment_structure`.

The stored parsed outputs established the root cause: the model copied relevant source phrases but included literal outer quotation-mark characters in every evidence string. The source contained the inner phrases without those characters. Both responses pass the full local structural/evidence validation when only that outer presentation pair is removed.

A test-first correction now performs this bounded normalization only when the original evidence is not a source substring and its inner text is an exact substring. Other non-exact evidence remains invalid. The prompt also explicitly tells the model not to add quotation-mark characters. The historical diagnostic outputs were revalidated locally; both now pass and retain the expected `POD` candidate.

The diagnostic also identified a separate semantic error: both outputs marked `bol_shipment_structure` present based only on a waybill reference, contrary to the feature's guardrail. This error was not normalized away. It demonstrates that strict structure and exact quote provenance do not establish semantic correctness, and supports requiring a class-specific combination in later deterministic sufficiency rules. No new full-control run was performed.

## 19. Task 1 — remaining-control rerun approved and bounded

The user approved an additional run for only `BOL`, `INVOICE`, and `OTHER`: three calls normally and no more than six with retry. The validated POD control will not be repeated.

**Original prompt (translated from Ukrainian):**

> Yes.

The runner now supports repeated `--only-source` arguments and cumulative prior-spend accounting. The already incurred $0.0377895 is passed explicitly. Before every call, the runner reserves the original conservative $0.0084 per-call planning bound and refuses to begin a call that could cross the cumulative $0.10 guardrail. This rerun has been prepared but not executed.

## 20. Task 1 — remaining-control results and semantic evidence findings

The user ran the approved `BOL`, `INVOICE`, and `OTHER` subset. Four calls cost an estimated $0.015702, bringing cumulative estimated spend to $0.0534915. INVOICE and OTHER completed local validation on their first calls with their expected candidates. Both BOL attempts selected the expected candidate but failed evidence validation because the transport-obligation quote replaced omitted source text with an ellipsis. One BOL quote also collapsed a PDF line break to a space.

Combined with the earlier POD diagnostic, all four simple controls received the expected candidate class. This demonstrates initial structured-classification feasibility but does not establish accuracy or routing reliability on a representative set.

Manual semantic review found recurring non-candidate false positives. In particular, `bol_shipment_structure` was present for all four classes based on generic shipment or route details. The transport invoice treated a delivery-date field as a completed delivery event, and the commercial invoice treated goods-valuation freight as a transport charge while also reporting multiple target purposes from its commercial-invoice identity. A simple total count of present features would therefore be misleading.

The result leaves two technical decisions for explicit review rather than silent implementation: continuous source evidence may reasonably allow whitespace normalization introduced by PDF extraction while still rejecting ellipses, and deterministic routing may need to use candidate-class critical combinations while deriving ambiguity/contradiction from those combinations instead of trusting model-reported cross-class diagnostics directly. No further API call was made.

## 21. Task 1 — deterministic sufficiency/routing experiment

The user approved a local deterministic routing experiment based on critical feature combinations and explicitly deferred any final production score or threshold.

**Original prompt (translated from Ukrainian):**

> Yes, I approve this direction. Move to the deterministic sufficiency/routing experiment based on critical feature combinations. Do not yet fix the final threshold/score as a ready production solution—first test the behavior of these rules on our controls and show the result.

Continuous evidence matching now allows PDF whitespace normalization while continuing to reject ellipses, paraphrases, and non-contiguous excerpts. Pure experiment rules define complete combinations for BOL, POD, INVOICE, and positive OTHER. Established complete BOL+POD evidence becomes uncertainty without fallback; incomplete or contradictory combinations escalate; model-supplied diagnostics remain advisory.

On the latest stored responses, POD, INVOICE, and OTHER pass provenance and receive `ACCEPT`. BOL has the expected candidate and a complete BOL combination, but its obligation evidence contains an ellipsis and therefore receives `ESCALATE` for invalid evidence. In Iteration 1 that escalation would temporarily become semantic `UNCERTAIN`.

Every control has a candidate match ratio of `1.0`, including the provenance-invalid BOL. The small simple set therefore cannot justify a numerical threshold or demonstrate score discrimination. The provenance gate and critical-combination rules provide useful behavior, while the final score, threshold, and routing quality remain deferred to systematic evaluation with incomplete, unclear, ambiguous, and contradictory examples.

Test-first synthetic cases cover complete acceptance, incomplete escalation, established combined BOL/POD, target contradiction for OTHER, and advisory-only model diagnostics. No additional API call was made.

## 22. Task 1 — minimal result contract and G1 review prepared

The user asked to complete point 8 of Task 1 and prepare the G1 review with factual results and limitations, without new API calls, starting Task 2, or creating a commit.

**Original prompt (translated from Ukrainian):**

> Continue with Task 1 according to the plan. Complete item 8, then prepare item 9—the G1 review with actual results and limitations. Do not make any new API calls, do not start Task 2 yet, and do not create a commit without my separate permission.

The proposed minimal logical result contract now separates model observations, provenance validation, backend-derived combinations, routing decisions, execution metadata, and technical failures. It requires that invalid provenance cannot be accepted, model diagnostics remain advisory, `OTHER` needs positive non-target evidence, a candidate class is not automatically final, and any future score is described as a routing signal rather than a probability. Exact Python types, persistence fields, score formula, and threshold remain deferred to G0 and Task 2E.

The Task 2E hypotheses now focus on candidate behavior per class, incorrect acceptance versus useful or unnecessary escalation, provenance versus semantic correctness, positive `OTHER`, combined BOL/POD handling, and whether any score discriminates on incomplete, unclear, ambiguous, and contradictory examples. The four current controls all have a candidate match ratio of `1.0`, so they do not support a threshold choice.

The prepared G1 recommendation is to accept the evidence-based architecture direction and minimal contract, without accepting production routing settings. Across 14 calls, the four simple controls all received the expected candidate class; the latest deterministic rules accept POD, INVOICE, and OTHER and escalate BOL because its required evidence contains an invalid ellipsis. Cumulative estimated spend was $0.0534915. The report records the small non-held-out set, semantic false positives, missing scanned/visual coverage, unresolved BOL provenance, lack of threshold discrimination, and prompt/validator revisions as explicit limitations.

A narrow prompt correction now explicitly prohibits ellipses and joining non-contiguous passages in evidence. Its contract test first failed and then passed after the wording was added. It was deliberately not live-tested under this instruction, so the G1 report marks it as an unverified post-run correction. Experiment identifiers are proposed for freezing only after the user's G1 approval. No API call, Task 2 work, or commit was performed.

## 23. Task 1 / G1 approved and closed

The user approved G1 for the architecture direction, minimal evidence-based result contract, and proposed experiment identifiers. The user explicitly did not approve a production score, threshold, or demonstrated routing quality; those remain deferred to systematic evaluation in Task 2E. The user requested that Task 1 be marked complete without starting Task 2 or creating a commit.

**Original prompt (translated from Ukrainian):**

> I approve G1: the architecture direction, the minimal evidence-based result contract, and the proposed experiment identifiers. The production score/threshold and demonstrated routing quality are not approved and remain for systematic evaluation in Task 2E. Record G1 as approved and mark Task 1 complete. Do not start Task 2 yet, and do not create a commit without my separate permission.

The G1 report now records the approval and its explicit boundary. The provider, endpoint, model, config, prompt, schema, and experimental routing-rules identifiers are frozen for the Task 1 artifact and exposed as constants in the standalone experiment modules; future sanitized summaries include the approved provider/endpoint/config/prompt/schema metadata. The implementation plan marks all Task 1 actions complete and leaves Task 2 untouched. No API call or commit was made.

## 24. Task 1 commit approved

The user explicitly approved committing the completed Task 1 changes.

**Original prompt (translated from Ukrainian):**

> Okay, let us commit the changes.

The reviewed commit contains the standalone AI feasibility experiment, deterministic routing probe, local extraction utility, tests, G1 report, completed Task 1 plan status, ignore rules for local artifacts, and mirrored engineering history. Local PDFs, extracted document text, API result files, virtual environments, IDE files, bytecode, and secrets remain outside Git. The commit message is `Complete Task 1 AI feasibility experiment`.
