from datetime import timedelta

from fraud_investigator.graph_analysis import make_graph_snippet, relationship_signals
from fraud_investigator.models import InvestigationCase, IngestResult, ReviewRequest, Signal, Transaction, utc_now
from fraud_investigator.simulator import TransactionSimulator
from fraud_investigator.storage import SQLiteStore


class InvestigationService:
    def __init__(self, store: SQLiteStore | None = None):
        self.store = store or SQLiteStore()
        self.simulator = TransactionSimulator()

    def ensure_demo_data(self) -> None:
        if self.store.metrics()["transactions"] == 0:
            self.reset_demo()

    def reset_demo(self) -> dict:
        self.store.clear()
        for transaction in TransactionSimulator.benign_seed():
            self.ingest(transaction)
        for transaction in TransactionSimulator.suspicious_scenario():
            self.ingest(transaction)
        return {"message": "Demo data reset and suspicious investigation replayed.", "metrics": self.store.metrics()}

    def replay_suspicious_scenario(self) -> list[IngestResult]:
        results = []
        for transaction in TransactionSimulator.suspicious_scenario():
            results.append(self.ingest(transaction))
        return results

    def ingest(self, transaction: Transaction) -> IngestResult:
        history = self.store.recent_transactions(transaction.timestamp - timedelta(days=30))
        signals = self._detect(transaction, history)
        self.store.save_transaction(transaction)
        case = self._open_or_update_case(transaction, signals) if signals else None
        return IngestResult(transaction=transaction, signals=signals, case=case)

    def generate_benign_transaction(self) -> IngestResult:
        return self.ingest(self.simulator.benign_transaction())

    def _detect(self, transaction: Transaction, history: list[Transaction]) -> list[Signal]:
        found: dict[str, Signal] = {}

        def add(code: str, title: str, detail: str, points: int) -> None:
            found[code] = Signal(code=code, title=title, detail=detail, points=points)

        two_minutes_ago = transaction.timestamp - timedelta(minutes=2)
        prior_outgoing = [
            item for item in history
            if item.sender_account == transaction.sender_account and item.timestamp >= two_minutes_ago
        ]
        outgoing = [*prior_outgoing, transaction]
        if len(outgoing) >= 5 and sum(item.amount for item in outgoing) >= 15000:
            add(
                "high_velocity",
                "High transaction velocity",
                f"{len(outgoing)} outgoing transfers totaling ${sum(item.amount for item in outgoing):,.2f} occurred within 2 minutes.",
                28,
            )

        small_transfers = [item for item in outgoing if item.amount < 2500]
        if len(small_transfers) >= 5 and sum(item.amount for item in small_transfers) >= 7000:
            add(
                "smurfing_pattern",
                "Repeated small transfers",
                f"{len(small_transfers)} transfers under $2,500 total ${sum(item.amount for item in small_transfers):,.2f} in 2 minutes.",
                24,
            )

        if transaction.receiver_account_age_days is not None and transaction.receiver_account_age_days <= 7 and transaction.amount >= 5000:
            add(
                "new_receiver_account",
                "Large transfer to a new account",
                f"${transaction.amount:,.2f} was sent to an account reported as {transaction.receiver_account_age_days} days old.",
                18,
            )

        account_history = [item for item in history if item.sender_account == transaction.sender_account]
        if transaction.amount >= 20000:
            add(
                "large_amount",
                "Unusually large transfer",
                f"The transfer amount is ${transaction.amount:,.2f}; review it in context of the account's activity.",
                16,
            )
        elif len(account_history) >= 4:
            amounts = sorted(item.amount for item in account_history)
            median = amounts[len(amounts) // 2]
            if median > 0 and transaction.amount >= median * 4:
                add(
                    "amount_spike",
                    "Transfer is high versus prior activity",
                    f"${transaction.amount:,.2f} is at least 4× the sender's prior median of ${median:,.2f}.",
                    18,
                )

        device_accounts = {
            account
            for item in history
            if item.device_id == transaction.device_id
            for account in (item.sender_account, item.receiver_account)
        }
        device_accounts.update((transaction.sender_account, transaction.receiver_account))
        if len(device_accounts) >= 3:
            add(
                "shared_device_cluster",
                "Device linked to multiple accounts",
                f"Device {transaction.device_id} appears in transactions involving {len(device_accounts)} accounts: {', '.join(sorted(device_accounts))}.",
                24,
            )

        graph_signals = relationship_signals(transaction, history)
        for code, detail in graph_signals:
            if code == "cycle_detected":
                add(code, "Transfer cycle detected", detail, 34)
            else:
                add(code, "Rapid onward transfer", detail, 20)

        return list(found.values())

    def _open_or_update_case(self, transaction: Transaction, signals: list[Signal]) -> InvestigationCase:
        accounts = {transaction.sender_account, transaction.receiver_account}
        case = self.store.find_open_case(accounts)
        if case:
            known = {signal.code for signal in case.signals}
            case.signals.extend(signal for signal in signals if signal.code not in known)
            if all(item.transaction_id != transaction.transaction_id for item in case.evidence_transactions):
                case.evidence_transactions.append(transaction)
            case.account_ids = sorted(set(case.account_ids) | accounts)
            case.updated_at = transaction.timestamp
            case.triggering_transaction_id = transaction.transaction_id
        else:
            case = InvestigationCase(
                triggering_transaction_id=transaction.transaction_id,
                account_ids=sorted(accounts),
                signals=signals,
                evidence_transactions=[transaction],
                priority_score=0,
                priority_band="Low",
                graph_data={},
                account_context={},
            )

        signature = self._signature(case.signals)
        feedback = self.store.feedback_counts(signature)
        adjustment = 0
        context_parts = []
        if feedback.get("legitimate", 0):
            amount = min(10, feedback["legitimate"] * 5)
            adjustment -= amount
            context_parts.append(f"{feedback['legitimate']} prior similar case(s) were marked legitimate (−{amount} priority points).")
        if feedback.get("confirmed_fraud", 0):
            amount = min(10, feedback["confirmed_fraud"] * 5)
            adjustment += amount
            context_parts.append(f"{feedback['confirmed_fraud']} prior similar case(s) were confirmed fraud (+{amount} priority points).")

        base_score = min(100, sum(signal.points for signal in case.signals))
        case.feedback_adjustment = adjustment
        case.feedback_context = " ".join(context_parts) or None
        case.priority_score = max(20, min(100, base_score + adjustment))
        case.priority_band = self._priority_band(case.priority_score)

        all_transactions = self.store.transactions_for_accounts(set(case.account_ids))
        case.evidence_transactions = self._dedupe_transactions([*case.evidence_transactions, *all_transactions])[:25]
        case.graph_data = make_graph_snippet(all_transactions, set(case.account_ids))
        case.account_context = self._account_context(set(case.account_ids), all_transactions)
        self.store.save_case(case)
        return case

    def _account_context(self, accounts: set[str], transactions: list[Transaction]) -> dict[str, dict]:
        context = {}
        for account in sorted(accounts):
            related = [item for item in transactions if account in (item.sender_account, item.receiver_account)]
            outgoing = [item.amount for item in related if item.sender_account == account]
            incoming = [item.amount for item in related if item.receiver_account == account]
            context[account] = {
                "transaction_count": len(related),
                "outgoing_count": len(outgoing),
                "incoming_count": len(incoming),
                "total_outgoing": round(sum(outgoing), 2),
                "total_incoming": round(sum(incoming), 2),
                "devices_seen": sorted({item.device_id for item in related}),
            }
        return context

    @staticmethod
    def _dedupe_transactions(transactions: list[Transaction]) -> list[Transaction]:
        unique = {item.transaction_id: item for item in transactions}
        return sorted(unique.values(), key=lambda item: item.timestamp, reverse=True)

    @staticmethod
    def _signature(signals: list[Signal]) -> str:
        return ",".join(sorted(signal.code for signal in signals))

    @staticmethod
    def _priority_band(score: int) -> str:
        if score >= 80:
            return "Critical"
        if score >= 60:
            return "High"
        if score >= 40:
            return "Medium"
        return "Low"

    def review_case(self, case_id: str, request: ReviewRequest) -> InvestigationCase | None:
        case = self.store.get_case(case_id)
        if not case:
            return None
        signature = self._signature(case.signals)
        return self.store.record_review(case, request, signature)
