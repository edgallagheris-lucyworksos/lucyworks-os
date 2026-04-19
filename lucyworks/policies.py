import pandas as pd

ERROR_SEVERITY = [
    {"severity": "MINOR", "definition": "Non-safety issue", "action": "Log and proceed"},
    {"severity": "MODERATE", "definition": "Workflow or risk issue", "action": "Require human review"},
    {"severity": "CRITICAL", "definition": "Escalation required", "action": "Block LIVE until resolved"},
]

LIVE_GATES = [
    {"rule": "reviewer identity missing", "effect": "block"},
    {"rule": "high rota risk without reason", "effect": "block"},
    {"rule": "safeguarding escalation not acknowledged", "effect": "block"},
    {"rule": "discharge approval missing clinician name", "effect": "block"},
]


def show_policies(st):
    st.subheader("Policy Tables")
    st.markdown("### Error severity")
    st.table(pd.DataFrame(ERROR_SEVERITY))
    st.markdown("### LIVE gates")
    st.table(pd.DataFrame(LIVE_GATES))
