# Four-Part Hackathon Task Breakdown

This plan splits the existing Trace project into four coordinated workstreams. The current application is a local hackathon prototype that uses synthetic transactions; task ownership does not imply that it is ready for real financial data.

## Current code map

- `app.py` starts the Streamlit analyst dashboard.
- `src/fraud_investigator/dashboard.py` implements the dashboard screens and interactions.
- `src/api/main.py` exposes the local FastAPI interface.
- `src/fraud_investigator/models.py` defines validated data models.
- `src/fraud_investigator/simulator.py` generates synthetic normal and suspicious scenarios.
- `src/fraud_investigator/service.py` handles ingestion, rules, case grouping, evidence, and review feedback.
- `src/fraud_investigator/graph_analysis.py` finds account relationship patterns with NetworkX.
- `src/fraud_investigator/storage.py` persists transactions, cases, and reviews in SQLite.
- `tests/test_service.py` covers service behavior.
- `docs/` contains architecture, decisions, and the demo script; `scripts/pre_submit.ps1` runs pre-submission checks.

The root-level `api/` and `fraud_investigator/` folders are currently empty. The active Python packages live under `src/`.

## Task 1 — Research, product scope, architecture, and README

**Owner profile:** product/research lead or documentation lead.

**Owns:** `README.md`, `docs/architecture.md`, `docs/decisions.md`, `docs/demo-script.md`, and this task plan. Coordinate any shared edits to `CONTRIBUTING.md` with Task 4.

**Work:**

- Restate the problem, target analyst, and end-to-end user journey.
- Keep the scope aligned with self-directed fraud investigations: synthetic monitoring, explainable signals, linked evidence, analyst review, and cautious feedback.
- Document the architecture, data flow, API/service boundaries, setup steps, demo scenario, assumptions, and limitations.
- Agree with Tasks 2 and 3 on the fields and service/API contracts before parallel implementation.
- Avoid claiming advanced AI, real-time bank feeds, regulatory certification, or production readiness unless actually implemented and verified.

**Done when:** a new teammate can install and run the demo using the README, explain where the sample data comes from, and present the case workflow using the demo script.

## Task 2 — Front end

**Owner profile:** Streamlit/UI developer.

**Owns:** `src/fraud_investigator/dashboard.py` and, when needed, the launch behavior in `app.py`.

**Work:**

- Maintain the top navigation and focused Overview, Alerts, Cases, Network, Learning, and Accounts workspaces.
- Make transaction signals, evidence, account links, case status, and analyst outcome controls easy to find and understand.
- Keep risk scores explainable and label them as prioritization signals, not proof of fraud.
- Handle empty, loading, and error states; make the main synthetic replay easy to demonstrate.
- Use the service layer and agreed model fields. Coordinate changes to shared service behavior with Task 3 instead of duplicating detection logic in the UI.

**Done when:** a reviewer can replay the scenario, open a case, inspect its evidence and graph, and record an outcome without needing to inspect the database manually.

## Task 3 — Back end

**Owner profile:** Python/API developer.

**Owns:** `src/api/main.py` and `src/fraud_investigator/{models.py,simulator.py,service.py,graph_analysis.py,storage.py}` plus `tests/test_service.py`.

**Work:**

- Keep simulator input, dashboard actions, and FastAPI requests flowing through the same service behavior.
- Maintain validation, explainable rules, NetworkX relationship analysis, case/evidence assembly, SQLite persistence, and review outcome handling.
- Keep feedback bounded and based only on reviewed outcomes; inconclusive reviews should not increase or decrease future priority.
- Maintain the documented API routes and agree on data fields with Task 2.
- Add or update focused service tests for ingestion, signal generation, case creation, review outcomes, and persistence.

**Done when:** the API docs load locally, sample and replay flows work, cases include traceable evidence, analyst outcomes persist, and service tests pass.

## Task 4 — Security, environment, Git, and release checks

**Owner profile:** security/release coordinator.

**Owns:** `.env.example`, `.gitignore`, `scripts/pre_submit.ps1`, and the release checklist in `README.md`. Coordinate contributor policy changes in `CONTRIBUTING.md` with Task 1.

**Work:**

- Keep this hackathon demo on synthetic data. Do not connect it to a bank or expose the local API/dashboard publicly.
- Verify `.env` files, credentials, generated SQLite databases, virtual environments, and caches are excluded from Git. `.env.example` is a sample and currently contains only a local database path; the app does not automatically load `.env` files.
- Be explicit that the prototype currently has no user authentication or role-based access and is not suitable for production financial data.
- Confirm the designated GitHub repository, visibility, collaborators, deadline/time zone, and submission format with the organizers.
- Review `git status`, `git diff`, staged changes, pre-submit checks, and test results before any commit or push. Each teammate must use their own GitHub account and make a genuine, meaningful contribution.

**Done when:** no secrets, real personal/financial data, or generated database files are staged; the checks pass; the official repository details are known; and every teammate's contribution is authentic and reviewable.

### Git setup commands

The project folder currently has no `.git` directory, so Git has not been initialized here yet. After confirming the official repository URL and reviewing the files to be committed, run these from Command Prompt:

```cmd
cd /d C:\Me\CODOWEEN_FINANCE_PROJECT
git init
git status
git add .
git status
git diff --cached
git commit -m "chore: prepare hackathon project"
git branch -M main
git remote add origin <OFFICIAL_REPOSITORY_URL>
git push -u origin main
```

Replace `<OFFICIAL_REPOSITORY_URL>` with the organizer-designated repository URL. Inspect the staged diff before committing. Do not add `.env`, database files, credentials, or generated artifacts. For team contribution rules, use each person's own account; do not share login credentials or create placeholder commits.

## Suggested 12-hour coordination

1. **Hour 0–1:** Task 1 locks scope and contracts; Task 4 confirms repository and submission requirements.
2. **Hours 1–7:** Tasks 2 and 3 build UI and service/API work in parallel against the agreed contract; Task 1 prepares docs and demo story.
3. **Hours 7–10:** Integrate the UI with the service, replay the scenario, review evidence and outcomes, and fix defects.
4. **Hours 10–11:** Task 4 checks secrets, Git diff, tests, and submission requirements; Task 1 finalizes README and demo script.
5. **Hour 11–12:** Capture the demo, commit genuine contributions, push to the confirmed repository, and submit the required link/form.

## Team handoff rules

- Assign one named owner per task and agree on a backup reviewer.
- Keep shared interfaces stable; tell the other owner before changing service methods or Pydantic fields.
- Make small, reviewable changes and communicate file ownership to reduce merge conflicts.
- Run the relevant checks after integration. Never represent a failed or unrun check as passing.

## Physical handoff folders

Use the four task briefs in [task pack index](../../README.md). Each folder identifies its scope and existing source files; application code stays in its canonical runtime paths to avoid duplicate copies and broken imports.


