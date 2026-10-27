import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fraud_investigator.models import InvestigationCase, ReviewRequest, Transaction


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "fraud_platform.sqlite3"


class SQLiteStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or os.getenv("FRAUD_DB_PATH", str(DEFAULT_DB)))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    sender_account TEXT NOT NULL,
                    receiver_account TEXT NOT NULL,
                    amount REAL NOT NULL,
                    device_id TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_transactions_sender ON transactions(sender_account);
                CREATE INDEX IF NOT EXISTS idx_transactions_receiver ON transactions(receiver_account);
                CREATE TABLE IF NOT EXISTS cases (
                    case_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    account_ids TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
                CREATE TABLE IF NOT EXISTS reviews (
                    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    note TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    signature TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(signature, outcome)
                );
                """
            )

    def clear(self) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM reviews")
            db.execute("DELETE FROM feedback")
            db.execute("DELETE FROM cases")
            db.execute("DELETE FROM transactions")

    def save_transaction(self, transaction: Transaction) -> None:
        payload = transaction.model_dump_json()
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO transactions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    transaction.transaction_id,
                    transaction.timestamp.isoformat(),
                    transaction.sender_account,
                    transaction.receiver_account,
                    transaction.amount,
                    transaction.device_id,
                    payload,
                ),
            )

    def list_transactions(self, limit: int = 500) -> list[Transaction]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM transactions ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [Transaction.model_validate_json(row["payload"]) for row in rows]

    def recent_transactions(self, since: datetime, limit: int = 1000) -> list[Transaction]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM transactions WHERE timestamp >= ? ORDER BY timestamp ASC LIMIT ?",
                (since.isoformat(), limit),
            ).fetchall()
        return [Transaction.model_validate_json(row["payload"]) for row in rows]

    def transactions_for_accounts(self, accounts: set[str], limit: int = 100) -> list[Transaction]:
        if not accounts:
            return []
        placeholders = ",".join("?" for _ in accounts)
        values = list(accounts)
        with self.connect() as db:
            rows = db.execute(
                f"SELECT payload FROM transactions WHERE sender_account IN ({placeholders}) "
                f"OR receiver_account IN ({placeholders}) ORDER BY timestamp DESC LIMIT ?",
                (*values, *values, limit),
            ).fetchall()
        return [Transaction.model_validate_json(row["payload"]) for row in rows]

    def recent_for_sender(self, account: str, since: datetime) -> list[Transaction]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM transactions WHERE sender_account = ? AND timestamp >= ? ORDER BY timestamp ASC",
                (account, since.isoformat()),
            ).fetchall()
        return [Transaction.model_validate_json(row["payload"]) for row in rows]

    def recent_incoming(self, account: str, since: datetime) -> list[Transaction]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload FROM transactions WHERE receiver_account = ? AND timestamp >= ? ORDER BY timestamp ASC",
                (account, since.isoformat()),
            ).fetchall()
        return [Transaction.model_validate_json(row["payload"]) for row in rows]

    def device_accounts(self, device_id: str, since: datetime) -> set[str]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT sender_account, receiver_account FROM transactions WHERE device_id = ? AND timestamp >= ?",
                (device_id, since.isoformat()),
            ).fetchall()
        return {account for row in rows for account in (row["sender_account"], row["receiver_account"])}

    def save_case(self, case: InvestigationCase) -> None:
        payload = case.model_dump_json()
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO cases VALUES (?, ?, ?, ?, ?, ?)",
                (
                    case.case_id,
                    case.created_at.isoformat(),
                    case.updated_at.isoformat(),
                    case.status,
                    json.dumps(case.account_ids),
                    payload,
                ),
            )

    def get_case(self, case_id: str) -> InvestigationCase | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        return InvestigationCase.model_validate_json(row["payload"]) if row else None

    def list_cases(self, status: str | None = None, limit: int = 200) -> list[InvestigationCase]:
        with self.connect() as db:
            if status:
                rows = db.execute(
                    "SELECT payload FROM cases WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT payload FROM cases ORDER BY updated_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [InvestigationCase.model_validate_json(row["payload"]) for row in rows]

    def find_open_case(self, account_ids: set[str]) -> InvestigationCase | None:
        for case in self.list_cases(status="open", limit=200):
            if account_ids.intersection(case.account_ids):
                return case
        return None

    def feedback_counts(self, signature: str) -> dict[str, int]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT outcome, count FROM feedback WHERE signature = ?", (signature,)
            ).fetchall()
        return {row["outcome"]: row["count"] for row in rows}

    def record_review(self, case: InvestigationCase, request: ReviewRequest, signature: str) -> InvestigationCase:
        reviewed_at = datetime.now(timezone.utc)
        case.status = "reviewed"
        case.outcome = request.outcome
        case.analyst_note = request.note.strip() or None
        case.reviewed_at = reviewed_at
        case.updated_at = reviewed_at
        with self.connect() as db:
            db.execute(
                "INSERT INTO reviews(case_id, outcome, note, reviewed_at) VALUES (?, ?, ?, ?)",
                (case.case_id, request.outcome, request.note.strip(), reviewed_at.isoformat()),
            )
            if request.outcome in {"confirmed_fraud", "legitimate"}:
                db.execute(
                    "INSERT INTO feedback(signature, outcome, count) VALUES (?, ?, 1) "
                    "ON CONFLICT(signature, outcome) DO UPDATE SET count = count + 1",
                    (signature, request.outcome),
                )
        self.save_case(case)
        return case

    def metrics(self) -> dict[str, int]:
        with self.connect() as db:
            transaction_count = db.execute("SELECT COUNT(*) AS n FROM transactions").fetchone()["n"]
            open_cases = db.execute("SELECT COUNT(*) AS n FROM cases WHERE status = 'open'").fetchone()["n"]
            reviewed = db.execute("SELECT COUNT(*) AS n FROM reviews").fetchone()["n"]
            legitimate = db.execute("SELECT COUNT(*) AS n FROM reviews WHERE outcome = 'legitimate'").fetchone()["n"]
        return {
            "transactions": transaction_count,
            "open_cases": open_cases,
            "reviewed_cases": reviewed,
            "legitimate_reviews": legitimate,
        }
