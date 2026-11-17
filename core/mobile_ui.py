"""Responsive presentation helpers for the APAA Android-first web interface."""

MOBILE_FIRST_CSS = r"""
/* Keep the same safe review workflows usable on narrow Android screens. */
[data-testid="stAppViewContainer"] .main .block-container {
    width: 100%;
    max-width: 1040px;
    padding-left: clamp(0.75rem, 3vw, 2rem);
    padding-right: clamp(0.75rem, 3vw, 2rem);
    padding-top: 1.25rem;
    padding-bottom: 3rem;
}

/* Touch targets and readable form controls. */
.stButton > button,
.stFormSubmitButton > button,
[data-testid="stSidebar"] button {
    min-height: 44px;
    min-width: 44px;
}
input, textarea, select,
[data-baseweb="input"] input,
[data-baseweb="textarea"] textarea {
    font-size: 16px !important;
}

/* Keep wide data/navigation elements from forcing page-level overflow. */
[data-testid="stDataFrame"],
[data-testid="stTable"],
.stTabs [data-baseweb="tab-list"] {
    max-width: 100%;
}
.stTabs [data-baseweb="tab-list"] {
    overflow-x: auto;
    flex-wrap: nowrap;
}

@media (max-width: 768px) {
    [data-testid="stAppViewContainer"] .main .block-container {
        max-width: 100%;
        padding-left: 0.85rem;
        padding-right: 0.85rem;
        padding-top: 0.75rem;
        padding-bottom: 5rem;
    }

    h1 { font-size: 1.65rem !important; line-height: 1.2 !important; }
    h2 { font-size: 1.35rem !important; line-height: 1.25 !important; }
    h3 { font-size: 1.12rem !important; }

    .stButton > button,
    .stFormSubmitButton > button {
        width: 100%;
        white-space: normal;
    }

    [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap;
        gap: 0.65rem;
    }

    [data-testid="stMetric"] {
        min-width: 0;
        overflow-wrap: anywhere;
    }

    [data-testid="stSidebar"] {
        max-width: min(88vw, 340px);
    }
}
"""


def apply_mobile_ui(streamlit_module) -> None:
    """Inject conservative responsive styles; no task or permission logic changes."""
    streamlit_module.markdown(
        f"<style>{MOBILE_FIRST_CSS}</style>",
        unsafe_allow_html=True,
    )
