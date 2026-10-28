from datetime import datetime, timedelta, timezone

import networkx as nx

from fraud_investigator.models import Transaction


def relationship_signals(transaction: Transaction, history: list[Transaction]) -> list[tuple[str, str]]:
    """Return explainable graph patterns involving the new transaction."""
    graph = nx.DiGraph()
    for item in history:
        graph.add_edge(item.sender_account, item.receiver_account, transaction_id=item.transaction_id)

    signals: list[tuple[str, str]] = []
    if transaction.sender_account != transaction.receiver_account and graph.has_node(transaction.receiver_account):
        if nx.has_path(graph, transaction.receiver_account, transaction.sender_account):
            try:
                path = nx.shortest_path(graph, transaction.receiver_account, transaction.sender_account)
                cycle = [transaction.sender_account, *path]
                signals.append((
                    "cycle_detected",
                    "A transfer path already connected the receiver back to the sender; this transaction closes a cycle: "
                    + " → ".join(cycle),
                ))
            except nx.NetworkXNoPath:
                pass

    # A short onward path is a useful investigation clue, not a conclusion.
    recent_cutoff = transaction.timestamp - timedelta(minutes=10)
    recent_incoming = [
        item for item in history
        if item.receiver_account == transaction.sender_account and item.timestamp >= recent_cutoff
    ]
    if recent_incoming:
        sources = sorted({item.sender_account for item in recent_incoming})
        signals.append((
            "rapid_onward_transfer",
            f"The sender received funds in the prior 10 minutes from {', '.join(sources)} and is now sending funds onward.",
        ))
    return signals


def make_graph_snippet(transactions: list[Transaction], focus_accounts: set[str]) -> dict:
    graph = nx.DiGraph()
    for item in transactions:
        if item.sender_account in focus_accounts or item.receiver_account in focus_accounts:
            graph.add_edge(
                item.sender_account,
                item.receiver_account,
                transaction_id=item.transaction_id,
                amount=item.amount,
                timestamp=item.timestamp.isoformat(),
                device_id=item.device_id,
            )
    nodes = [{"id": node, "label": node} for node in sorted(graph.nodes)]
    edges = [
        {
            "source": source,
            "target": target,
            "amount": float(data["amount"]),
            "timestamp": data["timestamp"],
            "transaction_id": data["transaction_id"],
            "device_id": data["device_id"],
        }
        for source, target, data in graph.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}
