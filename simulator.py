import random
from datetime import datetime, timedelta, timezone

from fraud_investigator.models import Transaction


class TransactionSimulator:
    def __init__(self, seed: int = 73):
        self.random = random.Random(seed)
        self.counter = 0

    def benign_transaction(self) -> Transaction:
        self.counter += 1
        sender = f"AC-{self.random.randint(1000, 9999)}"
        receiver = f"AC-{self.random.randint(1000, 9999)}"
        while receiver == sender:
            receiver = f"AC-{self.random.randint(1000, 9999)}"
        return Transaction(
            transaction_id=f"TX-LIVE-{self.counter:05d}",
            sender_account=sender,
            receiver_account=receiver,
            amount=round(self.random.uniform(35, 1250), 2),
            location=self.random.choice(["Pune, IN", "Mumbai, IN", "Bengaluru, IN", "Delhi, IN"]),
            device_id=f"DEV-{self.random.randint(10000, 99999)}",
        )

    @staticmethod
    def suspicious_scenario() -> list[Transaction]:
        now = datetime.now(timezone.utc)
        device = "DEV-SHARED-041"
        return [
            Transaction(
                transaction_id="TX-DEMO-1001",
                sender_account="AC-4101",
                receiver_account="AC-5202",
                amount=18400.00,
                timestamp=now - timedelta(minutes=3),
                location="Mumbai, IN",
                device_id=device,
                receiver_account_age_days=420,
            ),
            Transaction(
                transaction_id="TX-DEMO-1002",
                sender_account="AC-5202",
                receiver_account="AC-6303",
                amount=17950.00,
                timestamp=now - timedelta(minutes=2),
                location="Mumbai, IN",
                device_id=device,
                receiver_account_age_days=18,
            ),
            Transaction(
                transaction_id="TX-DEMO-1003",
                sender_account="AC-6303",
                receiver_account="AC-4101",
                amount=17100.00,
                timestamp=now - timedelta(minutes=1),
                location="Mumbai, IN",
                device_id=device,
                receiver_account_age_days=900,
            ),
        ]

    @staticmethod
    def benign_seed() -> list[Transaction]:
        now = datetime.now(timezone.utc)
        rows = []
        samples = [
            ("AC-1001", "AC-1002", 320.00, "DEV-HOME-12", "Pune, IN"),
            ("AC-1003", "AC-1004", 850.25, "DEV-OFFICE-08", "Delhi, IN"),
            ("AC-1002", "AC-1005", 95.00, "DEV-HOME-12", "Pune, IN"),
            ("AC-1006", "AC-1007", 1240.50, "DEV-SHOP-77", "Bengaluru, IN"),
            ("AC-1008", "AC-1009", 540.00, "DEV-HOME-29", "Mumbai, IN"),
        ]
        for index, (sender, receiver, amount, device, location) in enumerate(samples, start=1):
            rows.append(Transaction(
                transaction_id=f"TX-DEMO-{900 + index}",
                sender_account=sender,
                receiver_account=receiver,
                amount=amount,
                timestamp=now - timedelta(minutes=12 - index),
                location=location,
                device_id=device,
                receiver_account_age_days=120 + index * 21,
            ))
        return rows
