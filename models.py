from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Transaction(BaseModel):
    transaction_id: str = Field(default_factory=lambda: f"TX-{uuid4().hex[:10].upper()}")
    sender_account: str
    receiver_account: str
    amount: float = Field(gt=0)
    timestamp: datetime = Field(default_factory=utc_now)
    location: str = "Unknown"
    device_id: str = "unknown-device"
    receiver_account_age_days: int | None = Field(default=None, ge=0)


class Signal(BaseModel):
    code: str
    title: str
    detail: str
    points: int = Field(ge=0)


class InvestigationCase(BaseModel):
    case_id: str = Field(default_factory=lambda: f"CASE-{uuid4().hex[:8].upper()}")
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    status: Literal["open", "reviewed"] = "open"
    priority_score: int = Field(ge=0, le=100)
    priority_band: Literal["Low", "Medium", "High", "Critical"]
    triggering_transaction_id: str
    account_ids: list[str]
    signals: list[Signal]
    evidence_transactions: list[Transaction]
    graph_data: dict
    account_context: dict[str, dict]
    feedback_adjustment: int = 0
    feedback_context: str | None = None
    outcome: Literal["confirmed_fraud", "legitimate", "inconclusive"] | None = None
    analyst_note: str | None = None
    reviewed_at: datetime | None = None


class ReviewRequest(BaseModel):
    outcome: Literal["confirmed_fraud", "legitimate", "inconclusive"]
    note: str = Field(default="", max_length=1000)


class IngestResult(BaseModel):
    transaction: Transaction
    signals: list[Signal]
    case: InvestigationCase | None = None

