# Chatbot Architecture Notes (LangChain + LangGraph)

## Goal
Build a conversational chatbot that classifies a user request into a single predefined operation, collects missing/unclear inputs via clarification questions, creates an execution plan and gets user confirmation, executes (often via a subgraph), interprets results, validates outcomes, and returns a final user-facing response.

Constraint: **only one operation at a time** (no combining operations 2–3 together).

---

## High-level graph (top level)
### Recommended top-level stages
1. **Operation router / classifier**
   - Output: `operation_id` (one of predefined operations) + initial extracted arguments + ambiguity flags.
   - If user request contains multiple operations: ask user to pick exactly one.

2. **Operation subgraph dispatcher**
   - Route into an operation-specific subgraph (e.g., Control‑M vs Jenkins Deployment).

3. **Common cross-cutting nodes (owned by top-level graph)**
   - Clarification / slot-filling loop (callable from any stage).
   - Approval gates (plan approval, high-risk action confirmation).
   - Logging/audit metadata capture (who/when/what).
   - Error normalization (map tool errors to consistent error categories).

> Note: LangGraph supports human-in-the-loop pause/resume patterns that fit clarification and approval gates. [web:48]

---

## Clarification behavior (global)
Clarification should not be limited to “input collection only.”

Trigger clarification when:
- Required inputs are missing.
- An input is ambiguous (multiple jobs match, multiple run instances match, multiple envs, multiple Jenkins jobs, etc.).
- The plan has assumptions that need explicit confirmation.
- Execution errors are recoverable via user guidance (e.g., “Which instance should be used?”).

Behavior:
- Ask **one focused question at a time**.
- Store the answer into shared state.
- Resume from the same logical step after the answer.

---

## Plan + confirmation stage
Before any impactful action:
- Produce a short execution plan:
  - What will be changed.
  - Target identifiers (job name + run date + jobId, Jenkins job + env + version, etc.).
  - Preconditions checked / remaining.
  - Any manual steps required from the user.
  - Risks / side effects.
- Ask for explicit approval: proceed / cancel / modify.

---

## Execution stage (subgraph-friendly)
Execution may need multiple inner nodes:
- Pre-checks (permissions, current status, eligibility rules).
- Perform action (tool calls).
- Retry/backoff for transient failures.
- Collect outputs and normalize them to a consistent structure.

Followed by:
- **Result interpretation** (success/partial/failure + summary + raw references)
- **Post-validation** (did the system reach the intended state?)
- **Final response** (clear narrative + what was done + what user should do next)

---

# Operation 1: Control‑M Hold/Release (Run-date specific)

## Problem framing
- Jobs run for specific **run dates** (daily/weekly/monthly context).
- A job run instance for a given run date has a **jobId**.
- Hold/Release must be done for the specific run instance (jobId) for the requested run date.
- Before holding/releasing, fetch status of all relevant instances and validate conditions to determine if it is safe/allowed.

## Suggested subgraph stages
1. **Identify target job**
   - Resolve job identity (logical name/folder/application/etc.).
   - If multiple candidates: ask user to choose.

2. **Resolve run date**
   - Accept absolute date and (optionally later) relative phrases (today/yesterday/etc.).
   - Clarify if missing/ambiguous.

3. **Fetch run instances / statuses**
   - Query all run instances relevant to the requested run date (and possibly a time window).
   - Produce a list: `[ {jobId, status, heldFlag, runDate, ...} ]`.

4. **Eligibility check**
   - Apply your condition rules (e.g., “don’t hold if executing”, “don’t release if prerequisites not met”, etc.).
   - Produce eligible set + rejected set (with reasons).

5. **Plan + approval**
   - Show which jobIds will be held/released and why.
   - Ask for confirmation to proceed.

6. **Execute hold/release**
   - Perform action per eligible jobId.
   - Capture per-jobId outcome.

7. **Interpret + validate**
   - Re-check status to confirm hold/release actually applied.
   - Summarize results and any failures.

## Open questions to finalize later
- How users specify the job (name/folder/app/business key)?
- Does “run date” map to ODATE/ordering date in your environment?
- What exact condition rules gate hold/release?
- Handling multiple instances for same run date: auto-select or always ask?

---

# Operation 2: Jenkins Deployment (Change request or notes)

## Inputs
User provides either:
- **Change request number** (AskNow / change system) from which notes + attachments must be parsed, OR
- **Deployment notes** directly.

Notes/attachments typically include:
- Deployment options/parameters.
- Pre-deployment tasks.
- Deployment tasks.
- Post-deployment tasks.
- Validation tasks.

## User choice constraint
After intake, ask:
- “Which phase should be executed now: **pre / deploy / post / validate**?”

Only one phase is executed per run unless user explicitly approves a sequence.

## Task segregation
Parse and normalize into:
- `pre_tasks[]`
- `deploy_tasks[]`
- `post_tasks[]`
- `validation_tasks[]`

Each task should be tagged:
- `automatable: yes/no`
- `requires_user_action: yes/no`
- `required_inputs`
- `risk_level`

## Automation rules (current)
- In **pre tasks**, the bot can only automate **Control‑M hold/release** pieces (by calling Operation 1 subgraph).
- For other tasks, ask the user to do them manually.
  - Optionally generate a single shell script template the user can run to execute manual steps faster.
  - The bot should request confirmation/output after the user runs it.

Same rule applies for post/validation tasks:
- Automate only what is verifiable and safe; otherwise ask user to perform and confirm.

## Suggested Jenkins deployment subgraph stages
1. **Intake & parse**
   - If change number: pull notes + attachments, then extract tasks and parameters.
   - If direct notes: parse text.

2. **Clarify**
   - If parsing uncertain: ask user to confirm extracted tasks or fill missing parameters (env, version, service, etc.).

3. **Phase selection gate**
   - Ask whether to run pre/deploy/post/validate.

4. **Plan + approval**
   - Summarize the phase plan:
     - automated steps (e.g., Control‑M hold/release)
     - manual steps (with instructions and/or script template)
     - Jenkins deployment invocation (if applicable)
   - Ask for confirmation.

5. **Execute**
   - Run automatable steps.
   - For manual steps: pause and wait for user confirmation/results.

6. **Interpret + validate**
   - Confirm Jenkins outcome (success/failure) and any postchecks.
   - Provide final narrative response.

## Open questions to finalize later
- Required Jenkins targeting identifiers (app/service, env, version/artifact, region/cluster, Jenkins job name).
- Should the bot require proof/log snippets for manual steps or accept “done” as sufficient?
- If user picks “post” directly, should the bot require evidence that deployment happened (e.g., build number), or just warn?

---

## Shared state (conceptual)
Recommended shared state fields:
- `operation_id`
- `conversation_context`
- `inputs` (normalized key-value store)
- `missing_inputs[]`
- `plan` (human-readable + structured steps)
- `approval_status`
- `execution_results` (structured)
- `errors[]` (normalized categories)
- `validation_results`
- `final_message`

---

## Design principles
- Keep top-level graph responsible for routing + global clarification + approvals.
- Keep each operation’s logic inside its own subgraph.
- Represent every “need user input/approval” moment as a pause/resume checkpoint (human-in-the-loop). [web:48]
