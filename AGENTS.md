# Repository collaboration instructions

These instructions apply to all AI-assisted work in this repository.

## Decisions and scope

1. The user is the primary decision-maker for architecture, scope, implementation choices, and Git history. Discuss significant decisions with the user before implementing them.
2. If the user requests analysis, research, brainstorming, review, or planning only, do not modify the implementation unless explicitly asked to do so.
3. Do not overengineer. Do not introduce infrastructure, frameworks, abstractions, background workers, queues, databases, orchestration tools, or other dependencies unless they provide concrete value for the current requirements. Explain significant trade-offs before introducing them.
4. When proposing an architectural or technical decision, explain the reasoning, relevant alternatives, and why the proposed option is appropriate for this project. Do not silently make significant assumptions.
5. Keep implementation decisions understandable and reviewable. If introducing a non-obvious Django, Python, AI/LLM, OCR, or infrastructure mechanism, briefly explain what it does and why it is needed here.
6. Prefer iterative development: establish a small working vertical slice, verify it, identify limitations, and extend it based on concrete requirements rather than trying to build the entire system at once.

## Skills and workflow

7. Use the installed Superpowers skills selectively. Use Brainstorming before designing the solution and Planning only after the design is agreed. Do not automatically invoke additional workflows or add process ceremony unless they are useful for the current task.

## Workflow narrative files

8. `AI_WORKFLOW.md` and `AI_WORKFLOW_UA.md` are the user's own workflow narrative: manually authored and maintained by her (dictated and corrected over time), not an automated prompt/response log and not an AI-agent-owned artifact. Do not update, add to, rewrite, translate, or synchronize their content on your own initiative, and do not treat them as a prerequisite to read before other work. You may make a narrowly scoped change only when the user explicitly requests it and defines the scope (for example, formatting only, with no wording changes). Do not create a replacement repository logging file or process, automated or otherwise.

## Verification and Git history

9. **Prompt != commit.** A logical engineering stage may include analysis, discussion, implementation, failed verification, correction, and successful verification before one commit.
10. Do not make Git commits unless the user explicitly approves the commit. Before asking for approval, summarize the changes, show the verification/tests performed and their actual results, and propose a commit message.
11. Before declaring a stage complete, run the relevant available tests/checks and report the actual results. Do not claim something works without verification.

## Secrets

12. Never read, expose, print, commit, or include secret values from `.env`, environment variables, API keys, credentials, or similar sensitive configuration.

## Current status

The initial repository-instructions approval gate has already been completed. These instructions now govern ongoing implementation work.
