import streamlit as st

from core.approval import ApprovalManager
from core.tool_registry import build_default_registry

st.set_page_config(page_title="Tool Registry & Approvals | APAA", page_icon="🛡️", layout="wide")
st.title("🛡️ Tool Registry & Approval Queue")
st.caption("A capability catalog and explicit human-decision queue. This page does not execute tools.")

if "apaa_tool_registry" not in st.session_state:
    st.session_state["apaa_tool_registry"] = build_default_registry()
if "apaa_approval_manager" not in st.session_state:
    st.session_state["apaa_approval_manager"] = ApprovalManager(st.session_state["apaa_tool_registry"])

registry = st.session_state["apaa_tool_registry"]
manager = st.session_state["apaa_approval_manager"]

st.error(
    "Execution is disabled. Approving a request records a human decision only; "
    "it does not run a tool, open a website, modify a file, or trigger a background action."
)
st.info(
    "Ask first is the default. Auto-Run is unavailable. Payments, purchases, checkout, "
    "trading, money movement, credential access, and security-control changes are blocked."
)

st.subheader("Registered capability catalog")
st.dataframe(
    [
        {
            "Tool ID": item.tool_id,
            "Name": item.name,
            "Category": item.category,
            "Read only": "Yes" if item.read_only else "No",
            "Approval required": "Yes" if item.requires_approval else "No",
            "Execution": "Disabled",
        }
        for item in registry.list_tools()
    ],
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Registry entries are metadata only. No plugin loading, dynamic imports, handler "
    "dispatch, network calls, or execution adapters are attached."
)
st.divider()
st.subheader("Create an approval request")
eligible = [item for item in registry.list_tools() if item.category not in {
    "payment", "purchase", "checkout", "trading", "money_movement",
    "credential_access", "security_control_change",
}]
with st.form("apaa_approval_request_form", clear_on_submit=True):
    tool_id = st.selectbox(
        "Requested capability",
        options=[item.tool_id for item in eligible],
        format_func=lambda value: f"{value} — {registry.get(value).name}",
    )
    summary = st.text_area(
        "Describe the exact proposed action",
        max_chars=500,
        placeholder="Example: Inspect the selected local project archive without extracting files.",
    )
    submit = st.form_submit_button("Add to approval queue", disabled=not bool(eligible))

if submit:
    try:
        item = manager.request(tool_id, summary, {"summary": summary})
        st.success(f"Request created: {item.request_id[:12]} · expires at {item.expires_at}")
    except (ValueError, TypeError) as exc:
        st.error(str(exc))

st.divider()
st.subheader("Approval queue")
requests = manager.list_requests()
if not requests:
    st.info("No approval requests yet.")
else:
    for item in requests:
        with st.container(border=True):
            st.markdown(f"**{item.tool_id}** · {item.request_id[:12]}")
            st.write(item.summary)
            st.caption(
                f"Status: {item.status} · Created: {item.created_at} · "
                f"Expires: {item.expires_at}"
            )
            st.caption(f"Payload fingerprint (SHA-256): {item.payload_digest}")
            st.code(item.payload_preview, language="json")
            if item.decision_note:
                st.caption(f"Decision note: {item.decision_note}")
            if item.status == "pending":
                approve_col, reject_col = st.columns(2)
                if approve_col.button("Approve request", key=f"approve_{item.request_id}"):
                    try:
                        manager.decide(item.request_id, True, "Explicit approval in dashboard")
                        st.rerun()
                    except (KeyError, ValueError) as exc:
                        st.error(str(exc))
                if reject_col.button("Reject request", key=f"reject_{item.request_id}"):
                    try:
                        manager.decide(item.request_id, False, "Rejected in dashboard")
                        st.rerun()
                    except (KeyError, ValueError) as exc:
                        st.error(str(exc))

st.divider()
st.subheader("Current limitations")
st.markdown(
    "- Queue is held in Streamlit session state and is lost when that session ends.\n"
    "- Approval records are not yet connected to an executor; no action can be dispatched.\n"
    "- A request is descriptive metadata plus a payload fingerprint, not a complete "
    "typed execution contract.\n"
    "- Before any executor exists, the project still needs durable audit records, "
    "re-authentication/confirmation design, and independent security review."
)
st.caption("No paid APIs, paid services, external provider keys, or automatic paid fallback are used.")
