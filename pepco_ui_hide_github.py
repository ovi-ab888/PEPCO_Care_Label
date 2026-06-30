# pepco_ui_hide_github.py
# Hide Streamlit header/toolbar এ থাকা GitHub আইকন/লিংক
# ব্যবহার: st.set_page_config(...) এর ঠিক পরে
#   from pepco_ui_hide_github import hide_github
#   hide_github()            # শুধু GitHub আইকন hide
#   # hide_github(True)      # পুরো toolbar hide করতে চাইলে

from __future__ import annotations
import os
import streamlit as st

__all__ = ["hide_github"]

def hide_github(also_hide_toolbar: bool = False) -> None:
    """
    Streamlit top-right header/toolbar থেকে GitHub আইকন/লিংক লুকায়।
    also_hide_toolbar=True দিলে পুরো toolbar (সব আইকন) লুকিয়ে দেয়।
    পরিবেশ ভ্যারিয়েবল HIDE_ST_TOOLBAR="1" দিলে একই ফল (পুরো toolbar hide) হবে।
    """
    css = """
    <style>
    /* --- Robust selectors: header/toolbar/overflow menu --- */
    header[data-testid="stHeader"] a[href*="github.com"] { display: none !important; }
    div[data-testid="stToolbar"] a[href*="github.com"]   { display: none !important; }
    div[data-testid="stToolbar"] a[title*="GitHub"]      { display: none !important; }
    div[data-testid="stToolbar"] button[title*="GitHub"] { display: none !important; }
    div[data-testid="stToolbar"] a[aria-label*="GitHub"] { display: none !important; }
    /* Kebab / overflow menu items */
    ul[role="menu"] a[href*="github.com"]                { display: none !important; }
    /* Old selector fallback */
    #MainMenu a[href*="github.com"]                      { display: none !important; }

    /* Optional: nudge toolbar একটু ডানে */
    div[data-testid="stToolbar"] { right: 0.5rem; }
    </style>
    """
    # পুরো toolbar লুকাতে চাইলে
    if also_hide_toolbar or os.environ.get("HIDE_ST_TOOLBAR") == "1":
        css = css.replace(
            "</style>",
            "div[data-testid='stToolbar'] { display: none !important; } "
            "div[data-testid='stDecoration'] { display: none !important; } "
            "</style>"
        )

    st.markdown(css, unsafe_allow_html=True)
