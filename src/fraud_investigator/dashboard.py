"""Streamlit analyst workspace for the synthetic investigation platform."""

from collections import Counter, defaultdict

import pandas as pd
import streamlit as st

from fraud_investigator.models import ReviewRequest
from fraud_investigator.service import InvestigationService


PAGES = ["Overview", "Alerts", "Cases", "Network", "Learning", "Accounts"]
OUTCOME_LABELS = {
    "confirmed_fraud": "Confirmed fraud",
    "legitimate": "Legitimate",
    "inconclusive": "Inconclusive",
}


@st.cache_resource
def get_service() -> InvestigationService:
    return InvestigationService()


def money(value: float) -> str:
    return f"${value:,.2f}"


def timestamp(value) -> str:
    if not value:
        return "—"
    return value.strftime("%b %d · %H:%M UTC")


def transaction_rows(transactions) -> list[dict]:
    return [
        {
            "Time (UTC)": timestamp(item.timestamp),
            "Transaction": item.transaction_id,
            "From": item.sender_account,
            "To": item.receiver_account,
            "Amount": money(item.amount),
            "Location": item.location,
            "Device": item.device_id,
        }
        for item in transactions
    ]


def set_selected_case(case_id: str, key: str = "selected_case_id") -> None:
    st.session_state[key] = case_id


def choose_case(cases, key: str = "selected_case_id", label: str = "Select investigation"):
    ordered = sorted(
        cases,
        key=lambda item: (item.status != "open", -item.priority_score, item.updated_at),
    )
    options = [case.case_id for case in ordered]
    if not options:
        return None
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    by_id = {case.case_id: case for case in ordered}

    def format_case(case_id: str) -> str:
        case = by_id[case_id]
        accounts = ", ".join(case.account_ids[:3])
        if len(case.account_ids) > 3:
            accounts += f" +{len(case.account_ids) - 3}"
        return f"{case.priority_band} · {case.priority_score:02d} · {case.case_id} · {case.status.title()} · {accounts}"

    selected_id = st.selectbox(label, options, key=key, format_func=format_case)
    return by_id[selected_id]


def build_graphviz(case, include_devices: bool = True) -> str:
    def q(value) -> str:
        return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'

    lines = [
        "digraph Trace {",
        'graph [rankdir="LR", bgcolor="transparent", pad="0.2", nodesep="0.55", ranksep="0.8"];',
        'node [style="filled", color="#30435a", fillcolor="#142337", fontcolor="#e8eef6", fontname="Arial", penwidth="1.4"];',
        'edge [color="#57cdb4", fontcolor="#a9bacd", fontname="Arial", arrowsize="0.75", penwidth="1.5"];',
    ]
    for node in case.graph_data.get("nodes", []):
        lines.append(f"{q(node['id'])} [label={q(node['label'])}, shape=circle];")

    seen_devices = set()
    for edge in case.graph_data.get("edges", []):
        source, target = q(edge["source"]), q(edge["target"])
        label = money(float(edge.get("amount", 0)))
        lines.append(f"{source} -> {target} [label={q(label)}];")
        device_id = edge.get("device_id")
        if include_devices and device_id:
            device_node = f"device::{device_id}"
            if device_node not in seen_devices:
                seen_devices.add(device_node)
                lines.append(
                    f"{q(device_node)} [label={q('Device ' + device_id)}, shape=diamond, "
                    'fillcolor="#211c3b", color="#8b78e6"];'
                )
            lines.append(
                f"{source} -> {q(device_node)} [style=dashed, color=\"#7669b5\", "
                'arrowhead="none", constraint="false"];'
            )
            lines.append(
                f"{target} -> {q(device_node)} [style=dashed, color=\"#7669b5\", "
                'arrowhead="none", constraint="false"];'
            )
    lines.append("}")
    return "\n".join(lines)


def render_heading(title: str, subtitle: str, action=None) -> None:
    left, right = st.columns([4.3, 1.2], vertical_alignment="center")
    with left:
        st.markdown(f"## {title}")
        st.caption(subtitle)
    if action:
        with right:
            action()


def render_metrics(metrics: dict, cases) -> None:
    open_cases = [case for case in cases if case.status == "open"]
    signal_count = sum(len(case.signals) for case in cases)
    critical = sum(case.priority_band == "Critical" for case in open_cases)
    columns = st.columns(4)
    columns[0].metric("Transactions monitored", f"{metrics['transactions']:,}")
    columns[1].metric("Detection signals", f"{signal_count:,}")
    columns[2].metric("Open investigations", f"{len(open_cases):,}", f"{critical} critical")
    columns[3].metric("Analyst reviews", f"{metrics['reviewed_cases']:,}")


def render_case_summary(case) -> None:
    st.markdown(f"### {case.case_id}")
    a, b, c = st.columns(3)
    a.metric("Priority", f"{case.priority_score}/100", case.priority_band)
    b.metric("Status", case.status.title())
    c.metric("Connected accounts", len(case.account_ids))
    st.warning("Detection signals prioritize review. They do not prove fraud.")
    st.markdown("#### Why this case was raised")
    for signal in case.signals:
        st.markdown(f"**{signal.title}** · +{signal.points} priority points")
        st.caption(signal.detail)
    if case.feedback_context:
        st.info(f"Outcome feedback: {case.feedback_context} This case remains visible for analyst review.")

    if case.status == "reviewed":
        outcome = OUTCOME_LABELS.get(case.outcome, "Reviewed")
        st.success(f"Analyst outcome: {outcome}")
        if case.analyst_note:
            st.caption(f"Analyst note: {case.analyst_note}")
        return

    st.markdown("#### Analyst decision")
    note = st.text_area(
        "Review note (optional)",
        key=f"review-note-{case.case_id}",
        placeholder="Add the reasoning behind this outcome",
        height=75,
    )
    fraud, legitimate, inconclusive = st.columns(3)
    if fraud.button("Confirm fraud", type="primary", key=f"review-fraud-{case.case_id}", use_container_width=True):
        get_service().review_case(case.case_id, ReviewRequest(outcome="confirmed_fraud", note=note))
        st.rerun()
    if legitimate.button("Mark legitimate", key=f"review-legitimate-{case.case_id}", use_container_width=True):
        get_service().review_case(case.case_id, ReviewRequest(outcome="legitimate", note=note))
        st.rerun()
    if inconclusive.button("Needs more review", key=f"review-inconclusive-{case.case_id}", use_container_width=True):
        get_service().review_case(case.case_id, ReviewRequest(outcome="inconclusive", note=note))
        st.rerun()


def render_case_page(cases) -> None:
    render_heading("Investigation cases", "Evidence-led dossiers from first detection through analyst review.")
    filters, queue = st.columns([1.1, 2.2])
    with filters:
        status_filter = st.selectbox("Case status", ["All", "Open", "Reviewed"], key="case-status-filter")
        query = st.text_input("Search account or case", key="case-search", placeholder="CASE-… or AC-…")
    filtered = cases
    if status_filter == "Open":
        filtered = [case for case in filtered if case.status == "open"]
    elif status_filter == "Reviewed":
        filtered = [case for case in filtered if case.status == "reviewed"]
    if query.strip():
        needle = query.strip().lower()
        filtered = [
            case for case in filtered
            if needle in case.case_id.lower() or any(needle in account.lower() for account in case.account_ids)
        ]
    with queue:
        case = choose_case(filtered, label="Investigation queue")
    if not case:
        st.info("No investigations match these filters. Replay the synthetic scenario to create a case.")
        return

    with st.container(border=True):
        st.markdown(f"**{case.priority_band} priority** · Updated {timestamp(case.updated_at)} · Trigger {case.triggering_transaction_id}")
        summary_tab, evidence_tab, network_tab = st.tabs(["Dossier", "Evidence", "Network"])
        with summary_tab:
            render_case_summary(case)
        with evidence_tab:
            st.markdown("#### Supporting transactions")
            rows = transaction_rows(sorted(case.evidence_transactions, key=lambda item: item.timestamp, reverse=True))
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=270)
            else:
                st.caption("No supporting transactions are attached yet.")
            st.markdown("#### Account activity context")
            context_rows = [
                {
                    "Account": account,
                    "Related transactions": info["transaction_count"],
                    "Sent": info["outgoing_count"],
                    "Received": info["incoming_count"],
                    "Total sent": money(info["total_outgoing"]),
                    "Total received": money(info["total_incoming"]),
                    "Devices seen": ", ".join(info["devices_seen"]),
                }
                for account, info in case.account_context.items()
            ]
            st.dataframe(pd.DataFrame(context_rows), hide_index=True, use_container_width=True, height=210)
        with network_tab:
            include_devices = st.toggle("Show shared-device nodes", value=True, key=f"case-devices-{case.case_id}")
            if case.graph_data.get("edges"):
                st.graphviz_chart(build_graphviz(case, include_devices), use_container_width=True)
            else:
                st.caption("No relationship edges available for this case.")


def render_overview(metrics: dict, cases, transactions) -> None:
    def replay_action():
        if st.button("Replay suspicious scenario", type="primary", use_container_width=True):
            get_service().replay_suspicious_scenario()
            st.rerun()

    render_heading("Monitoring overview", "A live view of synthetic transaction activity and analyst investigations.", replay_action)
    render_metrics(metrics, cases)
    left, right = st.columns([1.6, 1])
    with left:
        st.markdown("### Live transaction stream")
        rows = transaction_rows(transactions[:8])
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=330)
        else:
            st.info("Waiting for simulated transactions.")
        st.caption("Synthetic records only · newest transactions first")
    with right:
        st.markdown("### Detection signals")
        counts = Counter(signal.title for case in cases for signal in case.signals)
        signal_rows = [{"Signal": key, "Cases": value} for key, value in counts.most_common()]
        if signal_rows:
            st.dataframe(pd.DataFrame(signal_rows), hide_index=True, use_container_width=True, height=190)
        else:
            st.caption("No signals have been raised.")
        st.markdown("### Priority queue")
        active = sorted((case for case in cases if case.status == "open"), key=lambda item: item.priority_score, reverse=True)
        if active:
            queue_rows = [
                {
                    "Priority": case.priority_band,
                    "Score": case.priority_score,
                    "Case": case.case_id,
                    "Accounts": ", ".join(case.account_ids),
                }
                for case in active[:4]
            ]
            st.dataframe(pd.DataFrame(queue_rows), hide_index=True, use_container_width=True, height=190)
        else:
            st.success("No open investigations.")


def render_alerts(cases) -> None:
    render_heading("Alerts triage", "Review explainable detection signals and open their supporting investigation dossiers.")
    rows = []
    case_by_id = {case.case_id: case for case in cases}
    for case in cases:
        for signal in case.signals:
            rows.append({
                "Detected": timestamp(case.created_at),
                "Case": case.case_id,
                "Signal": signal.title,
                "Type": signal.code.replace("_", " ").title(),
                "Priority": case.priority_band,
                "Score": case.priority_score,
                "Status": case.status.title(),
                "Accounts": ", ".join(case.account_ids),
                "Reason": signal.detail,
            })
    if not rows:
        st.info("No alerts yet. Run a transaction tick or replay the suspicious scenario.")
        return

    f_status, f_priority, f_search = st.columns([1, 1, 2])
    status_filter = f_status.selectbox("Status", ["All", "Open", "Reviewed"], key="alert-status-filter")
    priorities = ["All", "Critical", "High", "Medium", "Low"]
    priority_filter = f_priority.selectbox("Priority", priorities, key="alert-priority-filter")
    query = f_search.text_input("Search alerts", key="alert-search", placeholder="Signal, account, or case")
    filtered = rows
    if status_filter != "All":
        filtered = [row for row in filtered if row["Status"] == status_filter]
    if priority_filter != "All":
        filtered = [row for row in filtered if row["Priority"] == priority_filter]
    if query.strip():
        needle = query.strip().lower()
        filtered = [row for row in filtered if any(needle in str(value).lower() for value in row.values())]
    st.dataframe(pd.DataFrame(filtered), hide_index=True, use_container_width=True, height=410)

    available = list(dict.fromkeys(row["Case"] for row in filtered))
    if available:
        if st.session_state.get("alert-case-select") not in available:
            st.session_state["alert-case-select"] = available[0]
        selected = st.selectbox("Open evidence dossier", available, key="alert-case-select")
        if st.button("Review selected case", type="primary"):
            set_selected_case(selected)
            st.session_state["nav_page"] = "Cases"
            st.rerun()
    st.caption("An alert is a review lead, not a finding of fraud.")


def render_network(cases) -> None:
    render_heading("Relationship network", "Trace transfers and shared-device links across the selected case.")
    case = choose_case(cases, key="network_case_id", label="Case topology")
    if not case:
        st.info("Create or replay an investigation to see connected accounts.")
        return
    map_col, inspect_col = st.columns([2.1, 1])
    with map_col:
        include_devices = st.toggle("Include shared-device nodes", value=True, key=f"network-devices-{case.case_id}")
        if case.graph_data.get("edges"):
            st.graphviz_chart(build_graphviz(case, include_devices), use_container_width=True)
        else:
            st.info("No relationship edges are available.")
        cycles = [signal for signal in case.signals if signal.code == "cycle_detected"]
        if cycles:
            st.markdown("#### Cycle signals")
            for signal in cycles:
                st.warning(signal.detail)
        else:
            st.caption("No transfer cycle signal is recorded for this case.")
    with inspect_col:
        st.markdown("### Node inspector")
        accounts = case.account_ids
        account = st.selectbox("Inspect account", accounts, key=f"network-account-{case.case_id}")
        context = case.account_context.get(account, {})
        a, b = st.columns(2)
        a.metric("Sent", context.get("outgoing_count", 0))
        b.metric("Received", context.get("incoming_count", 0))
        st.caption(f"Total sent: {money(context.get('total_outgoing', 0))}")
        st.caption(f"Total received: {money(context.get('total_incoming', 0))}")
        st.markdown("**Devices observed**")
        devices = context.get("devices_seen", [])
        st.write(", ".join(devices) if devices else "No device identifiers")
        counterparties = sorted({
            edge["target"] if edge["source"] == account else edge["source"]
            for edge in case.graph_data.get("edges", [])
            if account in {edge["source"], edge["target"]}
        })
        st.markdown("**Connected accounts**")
        st.write(", ".join(counterparties) if counterparties else "No counterparties")
        st.caption("Account and device identifiers are synthetic demo values.")


def render_learning(cases) -> None:
    render_heading("Analyst feedback", "Outcome memory informs future prioritization without suppressing alerts or deciding fraud automatically.")
    reviewed = [case for case in cases if case.status == "reviewed"]
    outcomes = Counter(case.outcome for case in reviewed)
    metrics = st.columns(4)
    metrics[0].metric("Cases reviewed", len(reviewed))
    metrics[1].metric("Marked legitimate", outcomes.get("legitimate", 0))
    metrics[2].metric("Confirmed fraud", outcomes.get("confirmed_fraud", 0))
    metrics[3].metric("Inconclusive", outcomes.get("inconclusive", 0))
    st.info("Only reviewed confirmed-fraud and legitimate outcomes adjust future matching priorities. Adjustments are capped at ±10 points; all cases remain visible.")

    left, right = st.columns([1.15, 1])
    with left:
        st.markdown("### Reviewed signal patterns")
        patterns = defaultdict(Counter)
        signal_outcomes = defaultdict(Counter)
        for case in reviewed:
            signature = ", ".join(sorted(signal.code for signal in case.signals)) or "No signals"
            patterns[signature][case.outcome] += 1
            for signal in case.signals:
                signal_outcomes[signal.title][case.outcome] += 1
        pattern_rows = [
            {
                "Signal signature": signature,
                "Legitimate": counts.get("legitimate", 0),
                "Confirmed fraud": counts.get("confirmed_fraud", 0),
                "Inconclusive": counts.get("inconclusive", 0),
            }
            for signature, counts in patterns.items()
        ]
        if pattern_rows:
            st.dataframe(pd.DataFrame(pattern_rows), hide_index=True, use_container_width=True, height=260)
        else:
            st.caption("Reviewed outcomes will appear here as analysts close cases.")
    with right:
        st.markdown("### Outcome by signal")
        signal_rows = [
            {
                "Signal": name,
                "Legitimate": counts.get("legitimate", 0),
                "Confirmed fraud": counts.get("confirmed_fraud", 0),
                "Inconclusive": counts.get("inconclusive", 0),
            }
            for name, counts in signal_outcomes.items()
        ]
        if signal_rows:
            st.dataframe(pd.DataFrame(signal_rows), hide_index=True, use_container_width=True, height=260)
        else:
            st.caption("No signal outcomes have been reviewed yet.")

    adjusted = [case for case in cases if case.status == "open" and case.feedback_adjustment]
    st.markdown("### Current priority adjustments")
    adjustment_rows = [
        {
            "Case": case.case_id,
            "Adjustment": f"{case.feedback_adjustment:+d}",
            "Reason": case.feedback_context or "",
            "Current priority": f"{case.priority_score}/100 · {case.priority_band}",
        }
        for case in adjusted
    ]
    if adjustment_rows:
        st.dataframe(pd.DataFrame(adjustment_rows), hide_index=True, use_container_width=True)
    else:
        st.caption("No open case currently has a feedback-based priority adjustment.")


def render_accounts(cases, transactions) -> None:
    render_heading("Account risk directory", "Synthetic account activity, connected entities, and investigation context.")
    accounts = sorted({
        account
        for transaction in transactions
        for account in (transaction.sender_account, transaction.receiver_account)
    })
    if not accounts:
        st.info("No transaction accounts are available yet.")
        return

    activity = defaultdict(lambda: {
        "sent": 0, "received": 0, "total_sent": 0.0, "total_received": 0.0,
        "devices": set(), "counterparties": set(),
    })
    for item in transactions:
        activity[item.sender_account]["sent"] += 1
        activity[item.sender_account]["total_sent"] += item.amount
        activity[item.sender_account]["devices"].add(item.device_id)
        activity[item.sender_account]["counterparties"].add(item.receiver_account)
        activity[item.receiver_account]["received"] += 1
        activity[item.receiver_account]["total_received"] += item.amount
        activity[item.receiver_account]["devices"].add(item.device_id)
        activity[item.receiver_account]["counterparties"].add(item.sender_account)

    query = st.text_input("Search accounts or devices", placeholder="AC-… or DEV-…", key="account-search")
    filtered_accounts = accounts
    if query.strip():
        needle = query.strip().lower()
        filtered_accounts = [
            account for account in accounts
            if needle in account.lower() or any(needle in device.lower() for device in activity[account]["devices"])
        ]
    rows = []
    for account in filtered_accounts:
        linked_cases = [case for case in cases if account in case.account_ids]
        risk = max((case.priority_score for case in linked_cases), default=0)
        rows.append({
            "Account": account,
            "Sent": activity[account]["sent"],
            "Received": activity[account]["received"],
            "Total sent": money(activity[account]["total_sent"]),
            "Total received": money(activity[account]["total_received"]),
            "Devices": ", ".join(sorted(activity[account]["devices"])),
            "Linked accounts": len(activity[account]["counterparties"]),
            "Case risk priority": f"{risk}/100" if risk else "No linked case",
            "Cases": len(linked_cases),
        })
    rows.sort(key=lambda row: int(row["Case risk priority"].split("/")[0]) if "/" in row["Case risk priority"] else 0, reverse=True)
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True, height=400)

    if filtered_accounts:
        if st.session_state.get("account-profile") not in filtered_accounts:
            st.session_state["account-profile"] = filtered_accounts[0]
        selected = st.selectbox("Account profile", filtered_accounts, key="account-profile")
        profile = activity[selected]
        linked_cases = [case for case in cases if selected in case.account_ids]
        st.markdown(f"### {selected}")
        a, b, c, d = st.columns(4)
        a.metric("Transfers sent", profile["sent"])
        b.metric("Transfers received", profile["received"])
        c.metric("Linked accounts", len(profile["counterparties"]))
        d.metric("Linked investigations", len(linked_cases))
        if linked_cases:
            st.caption("Linked investigation cases: " + ", ".join(case.case_id for case in linked_cases))
        related = [
            item for item in transactions
            if selected in (item.sender_account, item.receiver_account)
        ][:8]
        st.markdown("#### Recent related transactions")
        st.dataframe(pd.DataFrame(transaction_rows(related)), hide_index=True, use_container_width=True, height=260)


def render_styles() -> None:
    st.markdown(
        """
        <style>
        :root { color-scheme: dark; }
        .stApp { background: radial-gradient(ellipse at 85% 0%, #0d252b 0, #0b1119 38%, #0b1119 100%); color: #e7edf5; }
        [data-testid="stHeader"] { background: rgba(10, 16, 25, .94); border-bottom: 1px solid #202d3e; }
        [data-testid="stAppViewContainer"] > .main .block-container { max-width: 1600px; padding: .7rem 1.6rem 2rem; }
        [data-testid="stSidebar"] { background: #101923; border-right: 1px solid #253241; }
        [data-testid="stMetric"] { background: linear-gradient(145deg, #121d2b, #101824); border: 1px solid #243346; border-radius: 14px; padding: 14px 16px; }
        [data-testid="stMetricLabel"] { color: #95a7bc; }
        [data-testid="stMetricValue"] { color: #f3f6fa; }
        [data-testid="stDataFrame"] { border: 1px solid #223146; border-radius: 12px; overflow: hidden; }
        [data-testid="stRadio"] [role="radiogroup"] { gap: 4px; flex-wrap: nowrap; overflow-x: auto; padding: 3px; }
        [data-testid="stRadio"] [role="radio"] { background: #121c29; border: 1px solid #253449; border-radius: 9px; padding: 6px 10px; white-space: nowrap; }
        [data-testid="stRadio"] [role="radio"]:has(input:checked) { background: #26336e; border-color: #7068e8; color: white; }
        .brand { padding: 3px 0 1px; line-height: 1.1; }
        .brand-name { font-size: 20px; font-weight: 800; letter-spacing: .04em; color: #f4f7fb; }
        .brand-tag { margin-top: 5px; color: #45d3bf; font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
        .section-kicker { color: #56d1bd; font-size: 11px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
        div[data-testid="stButton"] button { border-radius: 9px; border-color: #2b3a50; }
        div[data-testid="stButton"] button[kind="primary"] { border: 0; }
        div[data-testid="stTabs"] button { font-weight: 650; }
        @media (max-width: 1100px) {
          [data-testid="stAppViewContainer"] > .main .block-container { padding-left: .8rem; padding-right: .8rem; }
          [data-testid="stRadio"] [role="radiogroup"] { flex-wrap: wrap; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def run() -> None:
    st.set_page_config(page_title="Trace | Fraud Intelligence", page_icon="◉", layout="wide")
    render_styles()
    service = get_service()
    service.ensure_demo_data()

    brand_col, nav_col, live_col, tick_col, reset_col = st.columns([1.55, 6.2, 1.0, 0.72, 0.83])
    with brand_col:
        st.markdown(
            '<div class="brand"><div class="brand-name">◉ TRACE</div>'
            '<div class="brand-tag">Self-directed fraud investigations</div></div>',
            unsafe_allow_html=True,
        )
    with nav_col:
        page = st.radio(
            "Workspace navigation",
            PAGES,
            horizontal=True,
            label_visibility="collapsed",
            key="nav_page",
        )
    with live_col:
        st.toggle("Live", key="live_monitoring", help="Add a benign synthetic transaction every three seconds.")
    with tick_col:
        if st.button("Tick", help="Generate one benign synthetic transaction", use_container_width=True):
            service.generate_benign_transaction()
            st.rerun()
    with reset_col:
        if st.button("Reset", help="Restore the synthetic demo dataset", use_container_width=True):
            service.reset_demo()
            st.session_state.pop("selected_case_id", None)
            st.session_state.pop("network_case_id", None)
            st.rerun()
    st.divider()

    render_workspace(page)


@st.fragment(run_every="3s")
def render_workspace(page: str) -> None:
    service = get_service()
    if st.session_state.get("live_monitoring", False):
        service.generate_benign_transaction()
    metrics = service.store.metrics()
    cases = service.store.list_cases()
    transactions = service.store.list_transactions(limit=1000)

    if page == "Overview":
        render_overview(metrics, cases, transactions)
    elif page == "Alerts":
        render_alerts(cases)
    elif page == "Cases":
        render_case_page(cases)
    elif page == "Network":
        render_network(cases)
    elif page == "Learning":
        render_learning(cases)
    elif page == "Accounts":
        render_accounts(cases, transactions)
    st.caption("Trace uses synthetic data. Signals support analyst review and are not automatic fraud conclusions.")
