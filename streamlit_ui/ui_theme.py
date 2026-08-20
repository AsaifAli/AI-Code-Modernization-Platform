
"""Shared premium Streamlit visual layer for LegacyLens.\n\nPresentation-only: does not change application state, API calls, or business logic.\n"""
from __future__ import annotations
import streamlit as st


def apply_theme() -> None:
    """Apply a product-specific, system/Streamlit-theme-aware visual system."""
    try:
        mode = st.context.theme.type or "light"
    except Exception:
        mode = "light"
    dark = mode.lower() == "dark"
    if dark:
        tokens = dict(
            page="#080c14", surface="#0f1420", surface2="#151c2b", border="rgba(148,163,184,.18)",
            text="#f4f7fb", muted="#9aa7ba", faint="#718096", field="#111827",
            shadow="0 14px 42px rgba(0,0,0,.26)", tint="#4f46e514",
        )
    else:
        tokens = dict(
            page="#f7f8fc", surface="#ffffff", surface2="#f2f4f8", border="rgba(51,65,85,.14)",
            text="#172033", muted="#5f6b7d", faint="#7b8797", field="#ffffff",
            shadow="0 14px 36px rgba(15,23,42,.08)", tint="#4f46e50b",
        )
    accent1 = "#4f46e5"; accent2 = "#06b6d4"
    css = f"""
    <style>
    :root {{
      --ui-page:{tokens['page']}; --ui-surface:{tokens['surface']}; --ui-surface-2:{tokens['surface2']};
      --ui-border:{tokens['border']}; --ui-text:{tokens['text']}; --ui-muted:{tokens['muted']};
      --ui-faint:{tokens['faint']}; --ui-field:{tokens['field']}; --ui-shadow:{tokens['shadow']};
      --ui-accent:#4f46e5; --ui-accent-2:#06b6d4; --ui-tint:{tokens['tint'].format(accent1=accent1)};
    }}
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"] {{
      color: var(--ui-text); background: var(--ui-page);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    [data-testid="stHeader"] {{ background: transparent; }}

    /* Keep Streamlit's native sidebar collapse/expand control usable.
       Streamlit 1.38+ uses stSidebarCollapseButton (older releases used
       collapsedControl). */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="collapsedControl"],
    [data-testid="collapsedControl"] button {{
      display: flex !important;
      visibility: visible !important;
      opacity: 1 !important;
      pointer-events: auto !important;
      position: relative;
      z-index: 100000 !important;
    }}
    [data-testid="stToolbar"] {{ visibility:hidden; height:0; }}
    #MainMenu, footer {{ visibility:hidden; }}
    .block-container {{ max-width: 1440px; padding-top: 1.4rem; padding-bottom: 7rem; }}
    section[data-testid="stSidebar"] {{
      background: linear-gradient(180deg, var(--ui-surface), var(--ui-surface-2));
      border-right: 1px solid var(--ui-border);
    }}
    section[data-testid="stSidebar"] .block-container {{ padding-top: 1.25rem; }}
    [data-testid="stCaptionContainer"] {{ color: var(--ui-muted); }}
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li {{ color: var(--ui-text); }}
    [data-testid="stMarkdownContainer"] small {{ color: var(--ui-muted); }}
    h1, h2, h3 {{ letter-spacing:-.02em; color:var(--ui-text); }}
    h1 {{ font-weight: 800; }}
    h2, h3 {{ font-weight: 750; }}

    /* Buttons */
    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {{
      border-radius: 12px !important; border:1px solid var(--ui-border) !important;
      background: var(--ui-surface) !important; color: var(--ui-text) !important;
      box-shadow: 0 2px 8px rgba(15,23,42,.05); transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
      font-weight: 650;
    }}
    .stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {{
      transform: translateY(-1px); box-shadow: 0 8px 22px rgba(15,23,42,.10); border-color: var(--ui-accent) !important;
    }}
    .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {{
      background: linear-gradient(135deg, var(--ui-accent), var(--ui-accent-2)) !important; color:#fff !important;
      border-color: transparent !important; box-shadow: 0 10px 26px var(--ui-tint);
    }}

    /* Fields */
    div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div, div[data-baseweb="select"] > div,
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {{
      background: var(--ui-field) !important; color: var(--ui-text) !important;
      border-color: var(--ui-border) !important; border-radius: 12px !important;
    }}
    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="textarea"] > div:focus-within {{
      border-color: var(--ui-accent) !important; box-shadow: 0 0 0 3px var(--ui-tint) !important;
    }}
    [data-testid="stFileUploader"] section {{
      background: linear-gradient(180deg, var(--ui-surface), var(--ui-surface-2));
      border:1px dashed color-mix(in srgb, var(--ui-accent) 48%, var(--ui-border));
      border-radius: 16px; transition: border-color .18s ease, transform .18s ease, background .18s ease;
    }}
    [data-testid="stFileUploader"] section:hover {{ transform: translateY(-1px); border-color: var(--ui-accent); }}

    /* Cards / metrics / expanders */
    [data-testid="stMetric"] {{
      background: var(--ui-surface); border:1px solid var(--ui-border); border-radius:16px;
      padding:.85rem 1rem; box-shadow: var(--ui-shadow); transition: transform .18s ease, box-shadow .18s ease;
      animation: uiFadeUp .45s ease both;
    }}
    [data-testid="stMetric"]:hover {{ transform: translateY(-2px); }}
    [data-testid="stMetricValue"] {{ color:var(--ui-text); font-weight:800; }}
    [data-testid="stExpander"] {{ border:1px solid var(--ui-border) !important; border-radius:14px !important; background:var(--ui-surface) !important; overflow:hidden; }}
    [data-testid="stExpander"] summary:hover {{ background:var(--ui-tint); }}
    [data-testid="stTabs"] [role="tab"] {{ font-weight:650; color:var(--ui-muted); }}
    [data-testid="stTabs"] [aria-selected="true"] {{ color:var(--ui-text); }}

    /* Alerts */
    [data-testid="stAlert"] {{ border-radius:14px !important; border:1px solid var(--ui-border) !important; box-shadow: 0 6px 20px rgba(15,23,42,.05); animation: uiFadeUp .35s ease both; }}

    /* Chat surfaces */
    [data-testid="stChatMessage"] {{ animation: uiFadeUp .28s ease both; }}
    [data-testid="stChatInput"] > div {{
      background: var(--ui-surface) !important; border:1px solid var(--ui-border) !important;
      border-radius:18px !important; box-shadow: var(--ui-shadow) !important;
    }}
    [data-testid="stChatInput"] textarea {{ color:var(--ui-text) !important; background:transparent !important; }}

    /* Tables */
    [data-testid="stDataFrame"] {{ border:1px solid var(--ui-border); border-radius:14px; overflow:hidden; box-shadow: 0 8px 24px rgba(15,23,42,.05); }}

    /* Utility classes used by lightweight product-specific markup */
    .premium-panel {{ background:var(--ui-surface); border:1px solid var(--ui-border); border-radius:18px; padding:1rem 1.1rem; box-shadow:var(--ui-shadow); animation:uiFadeUp .42s ease both; }}
    .premium-kicker {{ text-transform:uppercase; letter-spacing:.14em; font-size:.72rem; font-weight:800; color:var(--ui-accent); }}
    .premium-chip {{ display:inline-flex; align-items:center; gap:.4rem; border:1px solid var(--ui-border); background:var(--ui-tint); color:var(--ui-text); border-radius:999px; padding:.35rem .65rem; font-size:.78rem; font-weight:700; margin:.15rem .25rem .15rem 0; }}
    .premium-muted {{ color:var(--ui-muted); }}
    @keyframes uiFadeUp {{ from {{ opacity:0; transform:translateY(6px); }} to {{ opacity:1; transform:none; }} }}
    @media (prefers-reduced-motion: reduce) {{ *, *::before, *::after {{ animation:none !important; transition:none !important; }} }}
    @media (max-width: 900px) {{ .block-container {{ padding-left:1rem; padding-right:1rem; }} }}
    </style>
    """
    st.html(css)
