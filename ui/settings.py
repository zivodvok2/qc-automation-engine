"""
ui/settings.py — Settings panel (rendered in sidebar expander)

Covers: theme selection, app version, onboarding relaunch,
feedback link, Ollama status, sign-in placeholder.
"""

import json
import streamlit as st
from pathlib import Path
from ui.onboarding import show_onboarding_button

VERSION_FILE = Path(__file__).parent.parent / "assets" / "app_version.json"
THEMES_FILE  = Path(__file__).parent.parent / "config"  / "themes.json"


def _load_version() -> dict:
    try:
        return json.loads(VERSION_FILE.read_text())
    except Exception:
        return {"version": "unknown", "changelog": []}


def _load_themes() -> dict:
    try:
        return json.loads(THEMES_FILE.read_text())
    except Exception:
        return {}


def _check_ollama() -> tuple[bool, list]:
    """Returns (is_available, available_models)."""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return True, models
    except Exception:
        pass
    return False, []


def init_settings():
    """Initialize settings state."""
    if "ds_theme" not in st.session_state:
        st.session_state.ds_theme = "dark"
    if "ds_ollama_model" not in st.session_state:
        st.session_state.ds_ollama_model = "llama3"


def render_settings():
    """
    Renders the settings panel inside a sidebar expander.
    Call from sidebar.py.
    """
    init_settings()
    version_data = _load_version()
    themes       = _load_themes()

    with st.sidebar.expander("⚙️ Settings", expanded=False):

        # ── Theme ─────────────────────────────────────────────────────────
        st.markdown("**Theme**")
        theme_names = {k: v["name"] for k, v in themes.items()} if themes else {"dark": "Dark"}
        selected_theme = st.selectbox(
            "Theme",
            options=list(theme_names.keys()),
            format_func=lambda k: theme_names[k],
            index=list(theme_names.keys()).index(st.session_state.ds_theme)
            if st.session_state.ds_theme in theme_names else 0,
            key="theme_select",
            label_visibility="collapsed",
        )
        if selected_theme != st.session_state.ds_theme:
            st.session_state.ds_theme = selected_theme
            st.rerun()

        st.divider()

        # ── Ollama / Verbatim ─────────────────────────────────────────────
        st.markdown("**Verbatim checks (Ollama)**")
        ollama_ok, ollama_models = _check_ollama()

        if ollama_ok:
            st.success(f"✓ Ollama running — {len(ollama_models)} model(s)")
            model_options = ollama_models if ollama_models else ["llama3"]
            st.session_state.ds_ollama_model = st.selectbox(
                "Model",
                options=model_options,
                index=0,
                key="ollama_model_select",
                label_visibility="collapsed",
            )
        else:
            st.warning("Ollama not detected")
            st.caption(
                "Install from [ollama.com](https://ollama.com) then run: `ollama pull llama3`"
            )

        st.divider()

        # ── Account (placeholder) ─────────────────────────────────────────
        st.markdown("**Account**")
        st.caption("Sign-in coming soon")
        col1, col2 = st.columns(2)
        col1.button("Sign in with Google", disabled=True, use_container_width=True)
        col2.button("Sign in with email",  disabled=True, use_container_width=True)

        st.divider()

        # ── Onboarding ────────────────────────────────────────────────────
        st.markdown("**Help**")
        show_onboarding_button()
        st.link_button(
            "📧 Send feedback",
            url="mailto:feedback@datasense.app?subject=DataSense Feedback",
            use_container_width=True,
        )

        st.divider()

        # ── Version / Changelog ───────────────────────────────────────────
        st.markdown(f"**DataSense v{version_data.get('version', '?')}**")
        st.caption(f"Released {version_data.get('release_date', '')}")
        with st.expander("Changelog"):
            for entry in version_data.get("changelog", []):
                st.caption(entry)


def get_theme_css(theme_key: str = "dark") -> str:
    """
    Returns CSS variable overrides for the selected theme.
    Inject this into st.markdown() at the top of app.py.
    """
    themes = _load_themes()
    t = themes.get(theme_key, themes.get("dark", {}))
    if not t:
        return ""

    return f"""
    <style>
    :root {{
        --ds-bg:       {t.get('bg',       '#0b0c0f')};
        --ds-surface:  {t.get('surface',  '#111318')};
        --ds-surface2: {t.get('surface2', '#181b22')};
        --ds-border:   {t.get('border',   '#1f2330')};
        --ds-accent:   {t.get('accent',   '#4af0a0')};
        --ds-text:     {t.get('text',     '#e8eaf2')};
        --ds-text2:    {t.get('text2',    '#8b90a8')};
        --ds-critical: {t.get('critical', '#f04a6a')};
        --ds-warning:  {t.get('warning',  '#f0c04a')};
        --ds-info:     {t.get('info',     '#4a9ef0')};
        --ds-head:     'Syne', sans-serif;
        --ds-mono:     'DM Mono', monospace;
    }}
    </style>
    """
