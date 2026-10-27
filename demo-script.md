# Judge demo script (about 90 seconds)

1. **Problem:** “Fraud clues often span transactions and accounts. Trace helps an analyst investigate those connections; it does not make the final fraud decision.”
2. **Detection:** Open the seeded case and point to the synthetic A → B → C → A transfer path and shared device.
3. **Evidence:** Show the signal explanations, linked transactions, timestamps, account context, and priority score.
4. **Human review:** Mark the case legitimate or inconclusive. Explain that an outcome is recorded and inconclusive cases do not update future priorities.
5. **Feedback:** Replay the scenario and show the bounded adjustment for a matching reviewed pattern. Emphasize that alerts remain visible.
6. **Architecture:** Mention the shared Python service, FastAPI endpoints, Streamlit analyst UI, NetworkX graph checks, and SQLite persistence.

All transaction and account data shown in this demo are synthetic.
