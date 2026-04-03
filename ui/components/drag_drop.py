"""
ui/components/drag_drop.py — Reusable column selector with drag-and-drop + CSV input

Provides a consistent column-picking UI used across QC, Logic, Straightlining, and EDA tabs.
Columns are displayed in a left panel; users drag them into target drop zones OR type them
as comma-separated values.
"""

import streamlit as st
import streamlit.components.v1 as components
from typing import Optional


def column_panel(df_columns: list, key_prefix: str = "col_panel") -> None:
    """
    Renders the left-side column panel with draggable column chips.
    Call this once at the top of any tab that uses drag-and-drop.

    Args:
        df_columns: list of column names from the loaded dataframe
        key_prefix: unique prefix to avoid widget key collisions between tabs
    """
    st.markdown(
        "<div style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
        "color:var(--ds-text2);margin-bottom:8px;font-weight:500;'>Available Columns</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='font-size:11px;color:var(--ds-text2);margin-bottom:12px;'>"
        "Drag into a target zone or type below</div>",
        unsafe_allow_html=True,
    )
    for col in df_columns:
        st.markdown(
            f"<div draggable='true' "
            f"data-col='{col}' "
            f"class='ds-col-chip' "
            f"style='cursor:grab;background:var(--ds-surface2);border:1px solid var(--ds-border);"
            f"border-radius:4px;padding:5px 10px;margin-bottom:4px;font-size:12px;"
            f"color:var(--ds-text);font-family:var(--ds-mono);white-space:nowrap;overflow:hidden;"
            f"text-overflow:ellipsis;user-select:none;'>{col}</div>",
            unsafe_allow_html=True,
        )


def drop_zone(
    label: str,
    key: str,
    default: str = "",
    help_text: str = "",
    multi: bool = True,
) -> list:
    """
    Renders a labeled drop zone with a text input fallback.
    Returns a list of selected column names.

    Args:
        label:     Zone label shown above the drop target
        key:       Unique streamlit widget key
        default:   Default comma-separated column names
        help_text: Small hint shown below
        multi:     If False, only allow one column (returns single-item list)
    """
    st.markdown(
        f"<div style='font-size:11px;letter-spacing:0.06em;text-transform:uppercase;"
        f"color:var(--ds-text2);margin-bottom:4px;'>{label}</div>",
        unsafe_allow_html=True,
    )

    placeholder = "e.g. Q1, Q2, Q3" if multi else "e.g. interviewer_id"
    raw = st.text_input(
        label,
        value=default,
        key=key,
        placeholder=placeholder,
        label_visibility="collapsed",
        help=help_text or ("Drag columns here, or type comma-separated names" if multi
                           else "Drag a column here, or type the column name"),
    )

    cols = [c.strip() for c in raw.split(",") if c.strip()]
    if not multi:
        cols = cols[:1]
    return cols


def column_multiselect(
    label: str,
    df_columns: list,
    key: str,
    default: Optional[list] = None,
    help_text: str = "",
) -> list:
    """
    A styled multiselect that shows all available columns.
    Used as the native Streamlit fallback when drag-and-drop is not needed.
    """
    return st.multiselect(
        label,
        options=df_columns,
        default=default or [],
        key=key,
        help=help_text,
    )


def inject_drag_drop_js() -> None:
    """
    Injects JavaScript that wires up HTML5 drag-and-drop between
    .ds-col-chip elements and st.text_input fields that serve as drop zones.

    Call this once per tab, after all drop_zone() calls.
    """
    components.html(
        """
        <script>
        (function() {
            function init() {
                // Find all draggable column chips
                const chips = document.querySelectorAll('.ds-col-chip');
                chips.forEach(chip => {
                    chip.addEventListener('dragstart', e => {
                        e.dataTransfer.setData('text/plain', chip.dataset.col);
                        chip.style.opacity = '0.5';
                    });
                    chip.addEventListener('dragend', e => {
                        chip.style.opacity = '1';
                    });
                });

                // Find all text inputs (drop zones rendered by drop_zone())
                const inputs = document.querySelectorAll(
                    'div[data-testid="stTextInput"] input'
                );
                inputs.forEach(input => {
                    input.addEventListener('dragover', e => {
                        e.preventDefault();
                        input.style.borderColor = '#4af0a0';
                        input.style.boxShadow   = '0 0 0 2px #4af0a020';
                    });
                    input.addEventListener('dragleave', e => {
                        input.style.borderColor = '';
                        input.style.boxShadow   = '';
                    });
                    input.addEventListener('drop', e => {
                        e.preventDefault();
                        const col = e.dataTransfer.getData('text/plain');
                        const current = input.value.trim();
                        const cols = current ? current.split(',').map(s => s.trim()) : [];
                        if (!cols.includes(col)) {
                            cols.push(col);
                        }
                        const nativeInputSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        ).set;
                        nativeInputSetter.call(input, cols.join(', '));
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                        input.style.borderColor = '';
                        input.style.boxShadow   = '';
                    });
                });
            }
            // Retry until DOM is ready (Streamlit re-renders asynchronously)
            let attempts = 0;
            const timer = setInterval(() => {
                if (document.querySelectorAll('.ds-col-chip').length > 0 || attempts > 20) {
                    clearInterval(timer);
                    init();
                }
                attempts++;
            }, 300);
        })();
        </script>
        """,
        height=0,
    )
