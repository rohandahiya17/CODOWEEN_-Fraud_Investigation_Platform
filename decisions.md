# Architecture decisions

## Synthetic data only

The hackathon demo uses generated transactions and fixed sample identifiers. This keeps the demo reproducible and avoids handling real financial or personal data.

## Explainable rules plus a graph

Rules and NetworkX graph checks are used because reviewers can inspect why an alert was raised. A rules-based prototype is not described as a trained AI system, and a risk score is a prioritization aid rather than a fraud verdict.

## SQLite for a shared local demo

SQLite keeps setup light while allowing Streamlit and FastAPI to share transaction, case, and review state. It can be replaced behind `SQLiteStore` if the project later needs a managed database.

## Bounded outcome feedback

Only reviewed confirmed-fraud and legitimate outcomes affect priority. Matching uses the exact signal-code signature, changes priority by at most 10 points, and never hides an alert. Inconclusive outcomes are recorded without changing future scoring. This keeps the feedback loop inspectable and limits overgeneralization from a single analyst decision.

## FastAPI and Streamlit share a service layer

The UI and API call the same `InvestigationService` so ingestion, scoring, case grouping, and feedback behavior stay consistent across the demo interfaces.

## Local demo security boundary

The prototype does not implement user authentication or role-based access. It is scoped to local synthetic-data demonstrations and should not be exposed as a live financial service.
