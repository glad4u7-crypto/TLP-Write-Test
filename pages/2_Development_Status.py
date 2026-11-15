import streamlit as st

st.set_page_config(
    page_title="Development Status | Autonomous AI Agent",
    page_icon="📍",
    layout="wide",
)

st.title("📍 APAA Development Status")
st.caption(
    "A transparent project tracker. This page separates implemented features, "
    "verified tests, parallel work, and items that are not yet ready."
)

st.info(
    "Zero-cost policy: this dashboard uses no paid API, paid provider, paid database, "
    "or automatic paid fallback. Status values below are a reviewed snapshot, not "
    "live telemetry from GitHub or a deployment platform."
)

st.subheader("Current dashboard stage")
left, middle, right = st.columns(3)
left.metric("Dashboard foundation", "v0.4.0")
middle.metric("Dashboard branch", "repository-inspector-v0.1")
right.metric("Production readiness", "Not ready")

st.caption(
    "Dashboard source: feature/repository-inspector-v0.1 · "
    "Reviewed snapshot: 2026-11-15 · "
    "Reviewed branch head: 010326d22880a56b4165a578bdd4179409c8d2ea"
)

st.divider()
st.subheader("Implemented in the dashboard branch")
completed = [
    ("Streamlit dashboard shell", "Implemented"),
    ("Project Manager", "Implemented · browser-session storage only"),
    ("Deterministic offline task planner", "Implemented · no external model API"),
    ("Read-only ZIP Repository Inspector", "Implemented · bounded, non-executing inspection"),
    ("Provider-neutral interface", "Implemented · external providers remain disabled"),
    ("Basic safety policy foundation", "Implemented · not a complete approval workflow"),
]
for name, detail in completed:
    st.markdown(f"- **{name}** — {detail}")

st.divider()
st.subheader("Verification evidence")
st.success(
    "GitHub Actions CI passed for dashboard commit "
    "010326d22880a56b4165a578bdd4179409c8d2ea (run #58, "
    "Agent Foundation CI; compile and foundation tests)."
)
st.markdown(
    "- CI result applies to the dashboard branch commit shown above; it does not "
    "certify the separate S09 browser-security branch.\n"
    "- Pull Request #3 is still **open and draft**; it has not been merged.\n"
    "- No live Streamlit deployment URL was confirmed in the last repository review."
)

st.divider()
st.subheader("Remaining dashboard work")
todo = [
    ("Persistent project storage", "Not started", "Projects currently disappear outside the active Streamlit session."),
    ("Tool Registry", "Not started", "No general tool catalog or controlled dispatch layer yet."),
    ("Execution queue", "Not started", "Tasks are planned, not dispatched to an execution worker."),
    ("Persistent memory", "Not started", "No durable agent memory store yet."),
    ("Audit log", "Not started", "No end-to-end durable action audit trail yet."),
    ("Approval UI", "Not started", "The policy foundation exists; a complete user-facing approval workflow does not."),
    ("Android usability qualification", "Not verified", "Must be tested on a real Android device/browser before claiming support."),
    ("Deployment", "Not verified", "A working public app URL has not been confirmed."),
]
for name, status, detail in todo:
    with st.container(border=True):
        col_a, col_b = st.columns([1, 1])
        col_a.markdown(f"**{name}**")
        col_b.markdown(f"**Status:** {status}")
        st.caption(detail)

st.divider()
st.subheader("Parallel browser-automation track")
st.warning(
    "APAA-S09-C01 is being developed on a separate branch "
    "(feature/apaa-s09-c01-p01-browser-launch). Its current checkpoint is "
    "APAA-S09-C01-P12-CONTINUE. The CONNECT proxy and pinned-IP egress work "
    "remain in progress; authored tests have not been reported as executed. "
    "Live browsing remains disabled while security blockers are open."
)
st.caption(
    "This parallel S09 work is not included in the dashboard branch snapshot above "
    "and must not be interpreted as an integrated or production-ready browser feature."
)

st.divider()
st.subheader("Next planned dashboard milestone")
st.markdown(
    "**Tool Registry + explicit approval workflow design.** "
    "Before execution is enabled, define tool permissions, approval boundaries, "
    "audit events, denial behavior, and offline tests. No real-site action or "
    "automatic execution is enabled by this status page."
)
st.caption(
    "Permission default remains Ask first. Auto-Run stays disabled. "
    "Payments, purchases, checkout, trading, money movement, paid APIs, and "
    "unapproved external mutations remain out of scope."
)
