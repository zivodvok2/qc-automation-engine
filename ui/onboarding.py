"""
ui/onboarding.py — First-time user onboarding tooltip system

Shows a dismissible step-by-step guide on first visit.
State is stored in st.session_state so it persists across reruns.
"""

import json
import streamlit as st
from pathlib import Path

STEPS_FILE = Path(__file__).parent.parent / "assets" / "onboarding_steps.json"


def _load_steps() -> list:
    try:
        return json.loads(STEPS_FILE.read_text())
    except Exception:
        return []


def init_onboarding():
    """Initialize onboarding state on first run."""
    if "onboarding_active" not in st.session_state:
        st.session_state.onboarding_active = True
        st.session_state.onboarding_step   = 0
    if "onboarding_dismissed" not in st.session_state:
        st.session_state.onboarding_dismissed = False


def render_onboarding():
    """
    Renders the onboarding tooltip overlay.
    Call this at the top of app.py, after init_onboarding().
    """
    init_onboarding()
    if st.session_state.onboarding_dismissed:
        return

    steps = _load_steps()
    if not steps:
        return

    step_idx = st.session_state.onboarding_step
    if step_idx >= len(steps):
        st.session_state.onboarding_dismissed = True
        return

    step = steps[step_idx]
    total = len(steps)

    # Progress dots
    dots = ""
    for i in range(total):
        if i == step_idx:
            dots += "● "
        else:
            dots += "○ "

    with st.container():
        st.markdown(
            f"""
            <div style="
                background: var(--ds-surface);
                border: 1px solid var(--ds-accent);
                border-radius: 10px;
                padding: 16px 20px;
                margin-bottom: 16px;
                position: relative;
            ">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                    <span style="font-size:1.2rem;">{step['icon']}</span>
                    <span style="font-family:var(--ds-head);font-weight:700;font-size:15px;
                                 color:var(--ds-text);">{step['title']}</span>
                    <span style="margin-left:auto;font-size:11px;color:var(--ds-text2);">
                        {step_idx + 1} / {total}
                    </span>
                </div>
                <p style="font-size:13px;color:var(--ds-text2);margin:0 0 12px 0;
                          line-height:1.6;">{step['body']}</p>
                <div style="font-size:12px;color:var(--ds-text2);letter-spacing:0.05em;">
                    {dots}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            if st.button("Skip guide", key="ob_skip", use_container_width=True):
                st.session_state.onboarding_dismissed = True
                st.rerun()
        with col2:
            if step_idx > 0:
                if st.button("← Back", key="ob_back", use_container_width=True):
                    st.session_state.onboarding_step -= 1
                    st.rerun()
        with col3:
            label = "Finish ✓" if step_idx == total - 1 else "Next →"
            if st.button(label, key="ob_next", use_container_width=True, type="primary"):
                if step_idx == total - 1:
                    st.session_state.onboarding_dismissed = True
                else:
                    st.session_state.onboarding_step += 1
                st.rerun()


def show_onboarding_button():
    """Small button to re-launch the guide — used in settings panel."""
    if st.button("Relaunch guide", use_container_width=True):
        st.session_state.onboarding_dismissed = False
        st.session_state.onboarding_step      = 0
        st.rerun()
