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

## Engineering record

8. Maintain a repository-level `AI_WORKFLOW.md` as a curated, human-readable record of meaningful AI-assisted engineering work. It is not a raw transcript.
9. For meaningful stages recorded in `AI_WORKFLOW.md`, preserve the user's original Ukrainian prompt and add an English translation immediately alongside it. Record important decisions, implementation changes, verification results, corrections/iterations, and the associated commit when applicable. If a prompt is supplied in another language, preserve the original; do not invent a Ukrainian original.
10. Do not add trivial learning questions or insignificant conversation to `AI_WORKFLOW.md`. Do not invent or retrospectively attribute reasoning or decisions to the user that the user did not make.
11. **Prompt != commit.** A logical engineering stage may include analysis, discussion, implementation, failed verification, correction, and successful verification before one commit.

## Verification and Git history

12. Do not make Git commits unless the user explicitly approves the commit. Before asking for approval, summarize the changes, show the verification/tests performed and their actual results, and propose a commit message.
13. Before each approved commit, update `AI_WORKFLOW.md` for the completed logical stage when appropriate, then include that update in the same commit.
14. Before declaring a stage complete, run the relevant available tests/checks and report the actual results. Do not claim something works without verification.

## Secrets

15. Never read, expose, print, commit, or include secret values from `.env`, environment variables, API keys, credentials, or similar sensitive configuration.

## Initial approval gate

For the initial repository-instructions step, create only this `AGENTS.md`. Do not initialize Django, install dependencies, implement application code, create `AI_WORKFLOW.md`, or make a Git commit. Do not proceed to project implementation until the user approves these instructions.
