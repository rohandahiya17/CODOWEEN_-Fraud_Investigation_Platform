import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fraud_investigator.models import ReviewRequest, Transaction
from fraud_investigator.service import InvestigationService
from fraud_investigator.storage import SQLiteStore


class InvestigationServiceTests(unittest.TestCase):
    def setUp(self):
        workspace_tests = Path(__file__).resolve().parent
        self.temp_dir = tempfile.TemporaryDirectory(dir=workspace_tests)
        self.service = InvestigationService(SQLiteStore(Path(self.temp_dir.name) / "test.sqlite3"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_benign_transaction_does_not_create_case(self):
        transaction = Transaction(
            transaction_id="TX-BENIGN-1",
            sender_account="AC-1111",
            receiver_account="AC-2222",
            amount=125.50,
            location="Pune, IN",
            device_id="DEV-ONLY-1",
        )
        result = self.service.ingest(transaction)
        self.assertEqual(result.signals, [])
        self.assertIsNone(result.case)

    def test_cycle_is_attached_to_investigation_evidence(self):
        now = datetime.now(timezone.utc)
        scenario = [
            Transaction(transaction_id="TX-A-B", sender_account="A", receiver_account="B", amount=500, timestamp=now - timedelta(minutes=2), device_id="D1"),
            Transaction(transaction_id="TX-B-C", sender_account="B", receiver_account="C", amount=450, timestamp=now - timedelta(minutes=1), device_id="D1"),
            Transaction(transaction_id="TX-C-A", sender_account="C", receiver_account="A", amount=400, timestamp=now, device_id="D1"),
        ]
        final_result = None
        for transaction in scenario:
            final_result = self.service.ingest(transaction)

        self.assertIsNotNone(final_result)
        self.assertIsNotNone(final_result.case)
        self.assertIn("cycle_detected", {signal.code for signal in final_result.case.signals})
        self.assertEqual(set(final_result.case.account_ids), {"A", "B", "C"})
        self.assertEqual(len(final_result.case.graph_data["edges"]), 3)

    def test_legitimate_review_moderately_reduces_matching_case_priority(self):
        self.service.reset_demo()
        demo_accounts = {"AC-4101", "AC-5202", "AC-6303"}
        demo_case = next(
            case for case in self.service.store.list_cases(status="open")
            if demo_accounts.issubset(set(case.account_ids))
        )
        self.service.review_case(demo_case.case_id, ReviewRequest(outcome="legitimate", note="Synthetic benign test disposition"))

        results = self.service.replay_suspicious_scenario()
        reviewed_pattern_case = next(
            result.case for result in reversed(results)
            if result.case and demo_accounts.issubset(set(result.case.account_ids))
        )
        self.assertEqual(reviewed_pattern_case.feedback_adjustment, -5)
        self.assertIn("prior similar case(s) were marked legitimate", reviewed_pattern_case.feedback_context)
        self.assertEqual(reviewed_pattern_case.status, "open")

    def test_inconclusive_review_does_not_create_feedback_adjustment(self):
        self.service.reset_demo()
        case = self.service.store.list_cases(status="open")[0]
        self.service.review_case(case.case_id, ReviewRequest(outcome="inconclusive"))
        self.assertEqual(self.service.store.feedback_counts(self.service._signature(case.signals)), {})


if __name__ == "__main__":
    unittest.main()
