from fastapi import FastAPI, HTTPException, Query

from fraud_investigator.models import InvestigationCase, IngestResult, ReviewRequest, Transaction
from fraud_investigator.service import InvestigationService


app = FastAPI(
    title="Self-Directed Fraud Investigation API",
    description="Synthetic transaction monitoring and analyst-led investigation demo.",
    version="0.1.0",
)
service = InvestigationService()
service.ensure_demo_data()


@app.get("/health")
def health():
    return {"status": "ok", "metrics": service.store.metrics()}


@app.get("/transactions", response_model=list[Transaction])
def transactions(limit: int = Query(default=100, ge=1, le=1000)):
    return service.store.list_transactions(limit=limit)


@app.post("/transactions", response_model=IngestResult)
def ingest_transaction(transaction: Transaction):
    return service.ingest(transaction)


@app.get("/cases", response_model=list[InvestigationCase])
def cases(status: str | None = Query(default=None, pattern="^(open|reviewed)$")):
    return service.store.list_cases(status=status)


@app.get("/cases/{case_id}", response_model=InvestigationCase)
def case_detail(case_id: str):
    case = service.store.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Investigation case not found")
    return case


@app.post("/cases/{case_id}/review", response_model=InvestigationCase)
def review_case(case_id: str, request: ReviewRequest):
    case = service.review_case(case_id, request)
    if not case:
        raise HTTPException(status_code=404, detail="Investigation case not found")
    return case


@app.post("/demo/transaction", response_model=IngestResult)
def generate_demo_transaction():
    return service.generate_benign_transaction()


@app.post("/demo/replay")
def replay_demo_scenario():
    return service.replay_suspicious_scenario()


@app.post("/demo/reset")
def reset_demo():
    return service.reset_demo()
