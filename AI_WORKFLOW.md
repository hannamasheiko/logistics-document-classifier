## Starting work on the assignment

On September 15 I started working on the take-home assignment: build a basic Django-based classifier for PDF documents from US logistics companies. The system had to recognize at least Invoice, Bill of Lading, and Proof of Delivery, return a confidence score, and, when needed, escalate to a more expensive or visual model. Field extraction with confidence for individual fields was listed as optional.

The assignment left substantial freedom in the technical implementation: no specific models, confidence calculation method, PDF/OCR stack, application structure, persistence, UI, or fallback criteria were specified. At the same time, the employer explicitly allowed active use of AI tools while completing the work.

So I decided to use AI not only for writing code, but also during research, design, and planning. My goal was to first form my own view of the solution, test it by discussing alternatives, and only then move on to implementation. I wanted to use AI as a technical sparring partner: to find weak points in my ideas, compare options, and check assumptions, while keeping the decisions about scope, architecture, and trade-offs for myself.

## Choosing an AI-assisted workflow

Before starting the design, I separately looked into how to organize this kind of process in Codex. For that, I enabled Superpowers — a set of workflow tools for brainstorming, planning, test-driven development, and other development stages.

For this assignment, Brainstorming specifically was the most useful: the assignment defined the end goal but left many open technical decisions. So instead of immediately asking AI to generate a Django project, I used this stage to work through the requirements, domain-specific nuances, and the future architecture step by step.

At the start, I also put together repository-level rules for the AI agent: significant architectural and scope decisions had to be agreed with me, the AI was not allowed to expand the system on its own without a concrete need, and non-trivial technical decisions had to be explained together with alternatives and trade-offs. This let me use an agentic workflow without handing the agent control over the system's own design.

## Brainstorming

Brainstorming started with breaking down the domain itself. One of the first questions was what exactly the classes INVOICE, BOL, POD, and OTHER should mean in the context of US logistics. I didn't want to build a classifier based only on document titles or random keywords, so I asked to check assumptions against real carrier forms and documentation.

During this stage we looked at examples from FedEx, UPS, DHL, XPO, and Old Dominion. This helped clarify that INVOICE in our taxonomy would mean billing specifically for transport or logistics services, while, for example, a Commercial Invoice for goods should fall under OTHER. It also became clear that BOL and POD can share many fields, and that real-world combined BOL/POD forms exist.

For combined BOL/POD, AI initially proposed simpler classification options, including assigning such a document to one of the main classes. I didn't want to artificially force an ambiguous document into BOL or POD, so after reviewing examples we settled on a separate semantic behavior: if the system reliably determines that a document is both a BOL and a POD at once, it returns UNCERTAIN with an explanation and does not trigger a fallback. If the system isn't sure whether it's a BOL, a POD, or a combined form, that's ordinary classification uncertainty and it can proceed to fallback.

Separately, we defined the boundaries of PDF processing. I chose a "one PDF — one document" model, allowed multi-page files, but limited the initial scope to ten pages and 10 MB. I also insisted that the system must not silently truncate a document that exceeds the limit. We initially decided to support text-layer PDFs, with scan support to be added as a mandatory next iteration through OCR.

A significant part of the brainstorming was about confidence. The initial discussion considered self-reported confidence from the LLM and logprobs, but I didn't want to present a model score as if it were a trustworthy probability of correctness. After a few iterations, I settled on a different direction: instead of the model saying "I'm 93% confident," it should return a candidate class together with class-specific evidence, and the backend should check that evidence and make the routing decision itself.

In the final design, this turned into the following principle:

> The LLM finds structured features and evidence in the document, and the backend deterministically decides whether they're sufficient to accept the classification.

This let us drop the requirement to compare multiple confidence mechanisms, logprobs, and self-reported scores. I also limited the scope of the research: for a take-home assignment, there was no point turning the task into a separate ML calibration project with dozens or hundreds of documents. Instead, we agreed to use a small representative evaluation set and check routing empirically.

Another decision was persistence. AI initially considered the simplest possible one-shot processing flow, but I didn't want to automatically simplify the system down to an API response with no history. I proposed storing the original PDF, metadata, the classification result, confidence, and model/fallback information, so a user could come back to a result and check it against the original. At the same time, I deliberately limited the scope: no authentication, user accounts, external object storage, deduplication, or complex infrastructure.

For relational data I chose PostgreSQL. SQLite would also have been enough for a take-home's functionality, but I already knew PostgreSQL well, and a minimal Docker Compose setup for the database didn't add significant implementation overhead. PDFs themselves stayed in Django's local media storage.

Throughout, I kept reining in the proposed complexity. During brainstorming we dropped or deferred background workers, queues, multi-provider research, a separate stronger-text fallback, a large calibration dataset, additional document classes, external storage, and other things that didn't provide enough value for the current scope.

As a result, Brainstorming ended not just with a set of ideas, but with an agreed high-level design: taxonomy, semantic uncertainty, text-first processing, OCR plus one visual fallback, evidence-based routing, persistence, PostgreSQL, a minimal UI/history, and planned field extraction once the core classifier was stable.

## Planning

After brainstorming, I moved on to formalizing the solution as an implementation plan. At this stage the task was no longer about generating new ideas, but about turning the agreed design into a sequence of small, verifiable stages.

I wanted to avoid a situation where the entire Django application gets built first, and the key assumption — whether these documents can even be reliably classified and yield evidence usable for routing — only gets checked at the very end. So the plan was built starting from the riskiest part of the system and working toward integration.

The first separate stage was an AI feasibility experiment. Its goal was to test the classification idea itself before any Django integration: can the model reliably tell BOL, POD, transport invoice, and OTHER apart, what features does it find, and can backend decisions be made based on those features.

The plan was then broken down into foundation, the production classification flow, UI/history, OCR and visual fallback, the full pipeline, and field extraction. I deliberately left some decisions deferred to their respective checkpoints — for example, not locking in a production threshold or fallback logic until experiment results were available.

I also didn't want the plan to turn into an overly complex production architecture. So during planning we removed or simplified things that weren't necessary for a take-home: unnecessary infrastructure, several alternative OCR stacks, a complex retention/deletion design, redundant manual test scenarios, and separate processes that didn't provide enough value for this scope.

The result was a plan where every major stage had its own goal and verification point. That made it possible to check after each step whether the assumption held, and only then move forward.

## Task 1 — verifying the primary classifier's feasibility

The first practical stage was checking, on its own, whether the chosen classification idea actually worked, before any Django integration. I wanted to check on real documents whether an LLM could tell BOL, POD, transport INVOICE, and OTHER apart, and whether it could return not just a class but structured features and evidence usable for later backend routing.

The experiment needed representative PDF documents. I searched for some examples manually through Google and official sources. We also tried delegating the document search to AI, but the results weren't reliable enough, so I still put together and checked the main set myself. As a result, quite a few PDFs ended up in the working chat, which AI read and analyzed directly in context.

During live checks, it became clear that a correct predicted class wasn't enough on its own. The model could identify a document correctly but sometimes gave weak or poorly formed evidence, and could interpret certain features too broadly. So I dropped the idea of relying on the LLM's self-reported confidence and settled on a different principle: the model returns a candidate class and class-specific evidence, and the backend checks that evidence and deterministically decides whether it's sufficient to accept the classification.

We also settled on separate rules for OTHER, combined BOL/POD, and contradictory results. Here I decided not to invent a numeric threshold on a small set just for the sake of having a confidence score — checking that was moved to a separate evaluation stage with a larger set of documents.

As a result, Task 1 confirmed the feasibility of the chosen approach and gave a basis for the production routing that followed. Gate 1 was approved after review.

### The problem with Codex allowance usage

At the same time, during Task 1 another problem became apparent — how quickly the available Codex limits were being used up.

This stage continued in the same large chat where Brainstorming and Planning had already taken place. Superpowers was connected and actively used there, a lot of prior context had accumulated, along with a large number of PDF documents and their analysis results. The Astra model was used for this work.

To understand the scale of the spend, I started separately tracking 5-hour and weekly allowance figures. At the start of active work on Task 1, roughly the following remained:

- 83% 5-hour allowance;
- 53% weekly allowance.

By the end of Task 1, roughly the following remained:

- 10% 5-hour allowance;
- 41% weekly allowance.

In other words, over roughly one working session the 5-hour meter dropped by 73 percentage points, and the weekly one by 12 points.

This was a problem not only because the current 5-hour window was nearly exhausted: it was clear that at this pace, the weekly budget would also run out quickly, with most of the implementation still ahead.

At this point I suspected that part of the spend might be tied not just to the complexity of the work itself, but to the accumulated context: the Superpowers workflow, the long Brainstorming/Planning history, the large number of PDFs read, and additional workflow documents.

So for the next stage I decided to run what was essentially a small practical experiment with the AI-assisted workflow itself:

- start Task 2 in a separate, new Codex thread;
- not use Superpowers unless specifically needed;
- explicitly forbid the agent from automatically applying its skills;
- not carry over the old PDFs or other large context into the new thread;
- not make Codex read old workflow logs;
- switch to GPT-5.6 Sol Medium;
- track 5-hour and weekly usage again, to compare spend against the previous session.

That closed out the first big work cycle, and Task 2 began with an updated, more compact approach to using Codex.

## Task 2 and Task 2E — foundation and systematic evaluation

I started Task 2 in a new Codex thread, without using Superpowers and without carrying over the large context from the previous session. GPT-5.6 Sol Medium was chosen for this work. Before starting, I again recorded usage: 100% of the 5-hour allowance and 40% of the weekly allowance remained.

During the Task 2 — Foundation Decisions stage, we locked in the production foundation for the Django application: PostgreSQL, PDF intake and validation, storing the original document, the ProcessingAttempt model, the processing lifecycle, and the main failure states. I specifically reviewed the proposed schema and simplified it wherever Codex was building in extra detail ahead of time — for example, not adding fallback-specific persistence before the fallback itself existed, and not creating unnecessary lifecycle states for a synchronous flow.

After the foundation, I moved on to Task 2E — systematic evaluation of the primary classifier. Here we were no longer just testing feasibility, but a concrete, production-oriented routing setup: the evidence score, the threshold, and the ACCEPT / ESCALATE / UNCERTAIN rules.

A separate document set was created for tuning, and live LLM calls were run against it. The results let us settle on the score as coverage of critical features, with a threshold of 1.0. The rules were then frozen and checked against a separate held-out set.

The first held-out run exposed a narrow problem — not in the routing, but in the prompt for OTHER: an EXPORT PACKING LIST and a PURCHASE ORDER were correctly recognized by the model as non-target by purpose, but didn't get the required explicit non_target_identity. Instead of loosening the threshold or tweaking the routing, I approved a targeted fix to the prompt/schema. The two examples already seen were moved into tuning, and a new held-out set was created for a fair re-check.

Held-out V2 passed cleanly: all 8 documents that were supposed to be accepted were correctly accepted; the incomplete invoice was correctly escalated; the combined BOL/POD document correctly came back as uncertain; there were no accepted errors and no unnecessary escalations. A manual evidence review also found a small limitation in the composite BOL evidence, which I decided to document rather than open a new research cycle over.

At this point Task 2E was closed, and the V2 prompt/schema, V1 routing rules, and the 1.0 threshold were frozen for the next integration stage.

### Re-assessing the AI agent's costs

In parallel, I kept tracking the Codex allowance. Over the course of Task 2 and Task 2E, the numbers moved like this:

- 5-hour: from 100% to 13%;
- weekly: from 40% to 27%.

So even after moving to a new thread, dropping Superpowers, and significantly cutting unnecessary context, a complex agentic workflow still burned through a large share of the available allowance.

Compared to the previous session, there was some improvement, but not a dramatic one. It became clear that the main source of spend wasn't just excess context anymore, but the working pattern itself: many cycles of read → reason → edit → run tests → inspect results → correct → verify, especially during evaluation and debugging.

This created a practical problem: the 5-hour allowance could run out in the middle of one implementation stage, after which I'd have to wait for it to reset. At the same time, the weekly allowance had already dropped to 27%, and by rough estimate it might not be enough for all the remaining stages.

So I decided to start using two coding agents from different AI providers — OpenAI Codex and Claude Code — as interchangeable working tools going forward. The idea wasn't to give them the same task at the same time, but to keep development sequential: work in one agent until it approaches its usage limit, and move the next logical stage to the other agent as needed, handing it the current state of the repository and the minimum necessary context.

I also decided to use the next task to observe costs in Claude Code specifically — record the starting and ending usage and compare how much resource a development stage of similar scale needs there. This was meant to help build a practical workflow where I'm not dependent on a single agent's allowance, while still keeping control over the sequence of development.

## Task 3 — switching to Claude Code

For Task 3 I carried out the switch planned at the end of Task 2E: instead of continuing in Codex, I started this stage in Claude Code — the exact approach of two interchangeable coding agents that I'd arrived at after repeatedly running into allowance limits. At the start of work on Task 3 in Claude Code, 100% of the 5-hour allowance and 100% of the weekly allowance were available.

The task itself was to implement the production modules for text classification, routing, and the attempt lifecycle — things that had previously only been verified in research code (`experiments/`) during Task 1 and Task 2E. The key technical decision: don't carry the research code straight into the application; instead, "port" the routing contract already frozen at Task 2E/GE (the model, the prompt/schema version, the routing rules, the acceptance threshold) into new production modules, without reinventing anything. The implementation followed the TDD order already agreed in the plan: first the tests for the routing logic, then the logic itself, then classification via OpenAI, then tests for the whole pipeline, and only then the pipeline itself.

During this work, AI deliberately declined to decide two things on its own and instead handed them to me. First — whether masking sensitive data (account numbers, SWIFT codes, and so on) was needed before sending document text to OpenAI; I decided to defer this as a purely additive change that doesn't break anything already written, so it wasn't worth spending time on given the limited time before the deadline. Second — when and how to run a live call against a real API key to check the integration, rather than just mock tests; I approved and ran that call myself, in my own terminal, with my own key, the same way this had already happened in Task 1 and Task 2E. The live test passed and confirmed real integration with OpenAI.

All automated tests (25) and the standard Django checks (`manage.py check`, `makemigrations --check --dry-run`) passed successfully; no commit was made without my separate confirmation.

By the end of Task 3, Claude Code had 79% of the 5-hour allowance and 97% of the weekly allowance left (i.e., 21% and 3% spent, respectively, from the original 100%/100%) — noticeably less than what comparable-scale stages had cost in Codex (for example, Task 1 took 73 percentage points of the 5-hour allowance and 12 points of the weekly one). A direct comparison is only approximate, since the volume and complexity of work differed between tasks, but the difference in spend rate was noticeable enough to record as an observation.

## Task 4 — first working UI and end-to-end verification

I continued Task 4 in the same Claude Code session I'd switched to for Task 3, and started it only after separately agreeing with AI that it would no longer move on to the next task on its own, only on my explicit instruction. The task itself was to finally connect the pipeline (classification + routing) already built in Task 3 to a real web interface — upload, result, and history pages, plus access to the original PDF. Up to this point, the pipeline had only existed as a standalone service that nothing had actually called over a real HTTP request yet.

During implementation, AI found and fixed a real bug on its own: the OpenAI client was being created right at the start of upload processing, before even trying to extract text from the PDF. That meant the client got created even in cases where the document was about to fail immediately at the extraction stage and no model call should have happened at all. The fix moved client creation to the point where it's actually needed.

I also actively controlled the live-verification process itself. Before allowing a failure scenario to be tested through the browser (not just a successful upload), I asked for confirmation that Django was running with `DEBUG=False` — I was worried that an unhandled exception could show a technical traceback page with environment variable values, including the API key, and that AI would be the one reading that page through its browser tool. AI confirmed the mode with a separate check (a plain 404 page instead of a technical one) before continuing. I kept the key itself strictly in my own `.env` file, outside git.

I started the server myself. In parallel, I also personally walked through the whole flow in my own browser: opened the upload page, uploaded `dhl_pod.pdf`, got a result with a status and label, then went to history and saw the same entry there. AI separately confirmed the same thing in an automated way, but through a different route: its built-in browser tool can't simulate picking a file through a native dialog, so it performed the actual upload on the server directly via an HTTP request (curl) with a real PDF file, and then checked the result/history/original pages through its own browser. So the flow was verified twice — manually by me, and separately in an automated way by AI — with a real call to OpenAI, not just against mock tests.

At the start of Task 4, 1% of the 5-hour allowance had been used, and right after finishing and committing — 12% (i.e., 11 percentage points spent on the task itself, leaving about 88%). The weekly allowance moved from 4% to 5% used over the same period.

## Task 5 — OCR and visual fallback (G2)

I also did Task 5 in Claude Code, continuing straight on from Tasks 3–4. This was a research gate (G2), like Task 1 had been earlier: the outcome is not production code, but a verified feasibility check and an agreed policy, which integration in Task 6 would only get with my separate approval.

Before writing anything, we went through each technical decision one at a time. For OCR, AI proposed pytesseract on top of the system Tesseract binary, and immediately and honestly flagged that the binary itself was a system-level change outside the `.venv`; I installed it myself via Homebrew. For rendering PDFs to images, AI first proposed pypdfium2 (already verified back in Task 1), but I asked to see an alternative — PyMuPDF — with real trade-offs (AGPL license versus a permissive one), and after that I confirmed the original proposal.

Most of the time went into the policy for "is there enough text to classify." AI proposed a simple length threshold (20 characters) to detect "a thin layer of text over an image." I wasn't willing to take a number on faith and asked to test it against a real example. We generated a synthetic page together — an image with a date and reference-number stamp over it — and the threshold immediately failed: a realistic stamp came out to 27 characters, above the 20-character threshold. Instead of picking a different number, AI proposed a different principle — always render the page and run OCR on it (it's local and free), and use whichever of the two texts is longer. This rule was checked against every available example, including that same boundary case, and it worked correctly everywhere.

For the visual fallback, I insisted on keeping the exact same set of features used for text, rather than simplifying it for images — my instinct was that simplifying it would only make the result worse. AI confirmed this technically: a vision model is just as capable of reading text in an image, so simplifying the feature set would only lose signal without any compensating benefit.

The live results confirmed the direction: on an example where local OCR produced pure garbage, the visual model read the document correctly on its own — that's the whole reason a fallback is worth having. On a deliberately even more degraded example (unreadable even to me personally — I checked the image myself, asking AI to show it before spending a call on it), the model honestly admitted it wasn't sure, instead of making up an answer.

Toward the end, AI broke its own rule of discussing things step by step: it wrote the section on timeout and retry behavior for the visual call on its own, without going through it with me first the way everything else in this task had been handled. I noticed this and asked to go back and cover it the same way as everything else.

At the start of Task 5, 14% of the 5-hour allowance and 5% of the weekly allowance had been used; at the time of this entry — 39% 5-hour and 8% weekly (i.e., 25 percentage points of the 5-hour allowance and 3 points of the weekly one spent on the task itself).

## Task 6 — production integration of OCR and visual fallback

I also did Task 6 in Claude Code, without breaking the session from Task 5. This was no longer a research gate, but carrying the approach agreed at G2 over into the real `documents/` pipeline.

Before implementation, we went through two specific open decisions that the plan hadn't pinned down. First — how many images of a document to send in a single visual call, for a multi-page document: I chose to send all pages at once in one call, rather than just the first page. Second — how to store the visual fallback's data in the database, since the existing model only had fields for the primary result: I chose to add separate `fallback_observations`/`fallback_metadata` fields with a migration, rather than cramming everything into the existing JSON field.

While testing against real (non-fake) fixtures from Task 5, AI found a serious gap on its own: if OCR found literally no text at all anywhere (not garbage — actually nothing), the old logic from Task 3/4 immediately marked the attempt as a technical failure, before any model call at all. That meant the visual fallback would never get a chance on exactly the worst scans, even though it exists specifically for cases like that. I decided to fix this: when there's no text at all, the system now still tries the visual fallback before giving up.

The most valuable part of this task happened during live browser verification, not in the tests. The very first real call to the already-frozen `gpt-5.4-mini-2026-03-17` model with `reasoning.effort="low"` started returning 404 — the third-party provider had apparently removed that reasoning tier specifically for this dated snapshot, sometime in the middle of our many-hour session. Before changing anything, I asked AI to clearly explain how much switching to `medium` would affect the tests already written; the answer was unambiguous — none of the 46 tests make live calls, so none of them would be affected. We agreed to first check this with a small confirmatory run, and only switch over fully once that succeeded — which is what we did. Right after that, a second, related side effect turned up: `medium` uses more reasoning tokens, and the old `max_output_tokens=1200` limit turned out to be too small for a real document — AI raised it to 2000 after measuring actual consumption.

After these fixes, the live check passed all three scenarios: a scanned document where OCR produced pure garbage, but the visual fallback correctly read the image and accepted the right class; a text document with incomplete evidence, where the fallback honestly confirmed uncertainty instead of making up an answer; and an established BOL/POD ambiguity, which correctly did not trigger the fallback at all.

At the start of Task 6, 39% of the 5-hour allowance and 8% of the weekly allowance had been used; at the time of this entry — 82% 5-hour and 14% weekly (i.e., 43 percentage points of the 5-hour allowance and 6 points of the weekly one spent on the task itself — noticeably more than on previous tasks, largely because of live-diagnosing unexpected problems on the model provider's side).
