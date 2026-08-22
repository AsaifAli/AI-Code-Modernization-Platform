"""Shared premium Streamlit visual layer for LegacyLens.

Theme-aware presentation-only layer. All product colors are derived from
Streamlit's live CSS theme tokens so switching Light/Dark/System in Settings
updates the workbench immediately without requiring a browser refresh.
"""
from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    """Apply a live Streamlit-theme-aware visual system.

    Do not read ``st.context.theme.type`` here. Streamlit documents that this
    value can be stale during a settings-menu theme change. Instead, the CSS
    consumes Streamlit's live ``--st-*`` theme variables, which update in the
    browser as the active theme changes.
    """
    css = """
    <style>
    /*
      LegacyLens theme tokens are defined on the live Streamlit app root,
      not :root. Streamlit scopes its --st-* theme variables below the document
      root, so defining derived tokens on :root can freeze the light fallback.
      The explicit data-theme selectors provide an immediate response when the
      user changes Streamlit Settings without a Python rerun; the media query
      covers system-level dark mode.
    */
    .stApp,
    [data-testid="stAppViewContainer"] {
      --ui-page: var(--st-background-color, #f7f8fc);
      --ui-surface: var(--st-secondary-background-color, #ffffff);
      --ui-surface-2: color-mix(in srgb, var(--ui-page) 72%, var(--ui-surface) 28%);
      --ui-border: var(--st-border-color, rgba(51,65,85,.14));
      --ui-text: var(--st-text-color, #172033);
      --ui-muted: color-mix(in srgb, var(--ui-text) 62%, transparent);
      --ui-faint: color-mix(in srgb, var(--ui-text) 44%, transparent);
      --ui-field: var(--st-secondary-background-color, #ffffff);
      --ui-primary: var(--st-primary-color, #4f46e5);
      --ui-accent: var(--st-primary-color, #4f46e5);
      --ui-accent-2: color-mix(in srgb, var(--ui-primary) 72%, #06b6d4 28%);
      --ui-tint: color-mix(in srgb, var(--ui-primary) 10%, transparent);
      --ui-shadow: 0 14px 36px color-mix(in srgb, var(--ui-text) 12%, transparent);
      --ui-hero-start: var(--ui-surface);
      --ui-hero-mid: color-mix(in srgb, var(--ui-surface) 72%, var(--ui-primary) 28%);
      --ui-hero-end: color-mix(in srgb, var(--ui-surface) 62%, #14b8a6 38%);
      --ui-hero-text: var(--ui-text);
      --ui-hero-muted: color-mix(in srgb, var(--ui-text) 68%, transparent);
      --ui-hero-border: color-mix(in srgb, var(--ui-border) 82%, transparent);
      --ui-hero-glow: color-mix(in srgb, var(--ui-primary) 22%, transparent);
      --ui-hero-chip-bg: color-mix(in srgb, var(--ui-primary) 9%, transparent);
      --ui-hero-chip-border: color-mix(in srgb, var(--ui-primary) 22%, var(--ui-border) 78%);
      --ui-success: var(--st-green-color, #16a34a);
      --ui-font: var(--st-font, Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif);
      color-scheme: light;
    }

    /* Immediate explicit dark-mode overrides for Streamlit's live theme marker. */
    [data-theme="dark"] .stApp,
    [data-theme="dark"] [data-testid="stAppViewContainer"],
    .stApp[data-theme="dark"],
    [data-testid="stAppViewContainer"][data-theme="dark"] {
      --ui-page: var(--st-background-color, #0b1020);
      --ui-surface: var(--st-secondary-background-color, #121a2b);
      --ui-surface-2: color-mix(in srgb, var(--ui-page) 72%, var(--ui-surface) 28%);
      --ui-border: var(--st-border-color, rgba(148,163,184,.22));
      --ui-text: var(--st-text-color, #f6f8ff);
      --ui-muted: color-mix(in srgb, var(--ui-text) 66%, transparent);
      --ui-faint: color-mix(in srgb, var(--ui-text) 46%, transparent);
      --ui-field: var(--st-secondary-background-color, #121a2b);
      --ui-primary: var(--st-primary-color, #22d3ee);
      --ui-accent: var(--st-primary-color, #22d3ee);
      --ui-accent-2: color-mix(in srgb, var(--ui-primary) 72%, #818cf8 28%);
      --ui-tint: color-mix(in srgb, var(--ui-primary) 12%, transparent);
      --ui-shadow: 0 18px 42px rgba(0,0,0,.28);
      --ui-hero-start: var(--ui-surface);
      --ui-hero-mid: color-mix(in srgb, var(--ui-surface) 68%, var(--ui-primary) 32%);
      --ui-hero-end: color-mix(in srgb, var(--ui-surface) 60%, #0f766e 40%);
      --ui-hero-text: var(--ui-text);
      --ui-hero-muted: color-mix(in srgb, var(--ui-text) 70%, transparent);
      --ui-hero-border: color-mix(in srgb, var(--ui-border) 84%, transparent);
      --ui-hero-glow: color-mix(in srgb, var(--ui-primary) 26%, transparent);
      --ui-hero-chip-bg: color-mix(in srgb, var(--ui-primary) 12%, transparent);
      --ui-hero-chip-border: color-mix(in srgb, var(--ui-primary) 28%, var(--ui-border) 72%);
      --ui-success: var(--st-green-color, #34d399);
      color-scheme: dark;
    }

    /* If Streamlit follows the OS directly, adapt even before its theme marker is present. */
    @media (prefers-color-scheme: dark) {
      .stApp,
      [data-testid="stAppViewContainer"] {
        --ui-page: var(--st-background-color, #0b1020);
        --ui-surface: var(--st-secondary-background-color, #121a2b);
        --ui-surface-2: color-mix(in srgb, var(--ui-page) 72%, var(--ui-surface) 28%);
        --ui-border: var(--st-border-color, rgba(148,163,184,.22));
        --ui-text: var(--st-text-color, #f6f8ff);
        --ui-muted: color-mix(in srgb, var(--ui-text) 66%, transparent);
        --ui-faint: color-mix(in srgb, var(--ui-text) 46%, transparent);
        --ui-field: var(--st-secondary-background-color, #121a2b);
        --ui-primary: var(--st-primary-color, #22d3ee);
        --ui-accent: var(--st-primary-color, #22d3ee);
        --ui-accent-2: color-mix(in srgb, var(--ui-primary) 72%, #818cf8 28%);
        --ui-tint: color-mix(in srgb, var(--ui-primary) 12%, transparent);
        --ui-shadow: 0 18px 42px rgba(0,0,0,.28);
        --ui-hero-start: var(--ui-surface);
        --ui-hero-mid: color-mix(in srgb, var(--ui-surface) 68%, var(--ui-primary) 32%);
        --ui-hero-end: color-mix(in srgb, var(--ui-surface) 60%, #0f766e 40%);
        --ui-hero-text: var(--ui-text);
        --ui-hero-muted: color-mix(in srgb, var(--ui-text) 70%, transparent);
        --ui-hero-border: color-mix(in srgb, var(--ui-border) 84%, transparent);
        --ui-hero-glow: color-mix(in srgb, var(--ui-primary) 26%, transparent);
        --ui-hero-chip-bg: color-mix(in srgb, var(--ui-primary) 12%, transparent);
        --ui-hero-chip-border: color-mix(in srgb, var(--ui-primary) 28%, var(--ui-border) 72%);
        --ui-success: var(--st-green-color, #34d399);
        color-scheme: dark;
      }
    }

    html, body, [data-testid="stAppViewContainer"], [data-testid="stMainBlockContainer"] {
      color: var(--ui-text);
      background: var(--ui-page);
      font-family: var(--ui-font);
    }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stToolbar"] { visibility:hidden; height:0; }
    [data-testid="stSidebarCollapseButton"], [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {
      opacity:1 !important; visibility:visible !important; pointer-events:auto !important; z-index:100001 !important;
    }
    [data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarCollapsedControl"] button, [data-testid="collapsedControl"] button {
      opacity:1 !important; visibility:visible !important; pointer-events:auto !important;
    }
    #MainMenu, footer { visibility:hidden; }
    .block-container { max-width: 1440px; padding-top: 1.4rem; padding-bottom: 7rem; }
    section[data-testid="stSidebar"] {
      background: linear-gradient(180deg, var(--ui-surface), var(--ui-surface-2));
      border-right: 1px solid var(--ui-border);
    }
    section[data-testid="stSidebar"] .block-container { padding-top: 1.25rem; }
    [data-testid="stCaptionContainer"] { color: var(--ui-muted); }
    [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li { color: var(--ui-text); }
    [data-testid="stMarkdownContainer"] small { color: var(--ui-muted); }
    h1, h2, h3 { letter-spacing:-.02em; color:var(--ui-text); font-family:var(--ui-font); }
    h1 { font-weight: 800; }
    h2, h3 { font-weight: 750; }

    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
      border-radius: 12px !important;
      border:1px solid var(--ui-border) !important;
      background: var(--ui-surface) !important;
      color: var(--ui-text) !important;
      box-shadow: 0 2px 8px color-mix(in srgb, var(--ui-text) 7%, transparent);
      transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
      font-weight: 650;
      font-family: var(--ui-font);
    }
    .stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {
      transform: translateY(-1px);
      box-shadow: 0 8px 22px color-mix(in srgb, var(--ui-text) 11%, transparent);
      border-color: var(--ui-accent) !important;
    }
    .stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {
      background: linear-gradient(135deg, var(--ui-accent), var(--ui-accent-2)) !important;
      color:var(--st-background-color, #fff) !important;
      border-color: transparent !important;
      box-shadow: 0 10px 26px var(--ui-tint);
    }

    div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div, div[data-baseweb="select"] > div,
    div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {
      background: var(--ui-field) !important;
      color: var(--ui-text) !important;
      border-color: var(--ui-border) !important;
      border-radius: 12px !important;
      font-family: var(--ui-font);
    }
    div[data-baseweb="input"] > div:focus-within, div[data-baseweb="textarea"] > div:focus-within {
      border-color: var(--ui-accent) !important;
      box-shadow: 0 0 0 3px var(--ui-tint) !important;
    }
    [data-testid="stFileUploader"] section {
      background: linear-gradient(180deg, var(--ui-surface), var(--ui-surface-2));
      border:1px dashed color-mix(in srgb, var(--ui-accent) 48%, var(--ui-border));
      border-radius: 16px;
      transition: border-color .18s ease, transform .18s ease, background .18s ease;
    }
    [data-testid="stFileUploader"] section:hover { transform: translateY(-1px); border-color: var(--ui-accent); }

    [data-testid="stMetric"] {
      background: var(--ui-surface); border:1px solid var(--ui-border); border-radius:16px;
      padding:.85rem 1rem; box-shadow: var(--ui-shadow);
      transition: transform .18s ease, box-shadow .18s ease; animation: uiFadeUp .45s ease both;
    }
    [data-testid="stMetric"]:hover { transform: translateY(-2px); }
    [data-testid="stMetricValue"] { color:var(--ui-text); font-weight:800; }
    [data-testid="stExpander"] { border:1px solid var(--ui-border) !important; border-radius:14px !important; background:var(--ui-surface) !important; overflow:hidden; }
    [data-testid="stExpander"] summary:hover { background:var(--ui-tint); }
    [data-testid="stTabs"] [role="tab"] { font-weight:650; color:var(--ui-muted); }
    [data-testid="stTabs"] [aria-selected="true"] { color:var(--ui-text); }
    [data-testid="stAlert"] { border-radius:14px !important; border:1px solid var(--ui-border) !important; box-shadow:0 6px 20px color-mix(in srgb, var(--ui-text) 7%, transparent); animation:uiFadeUp .35s ease both; }
    [data-testid="stChatMessage"] { animation:uiFadeUp .28s ease both; }
    [data-testid="stChatInput"] > div { background:var(--ui-surface) !important; border:1px solid var(--ui-border) !important; border-radius:18px !important; box-shadow:var(--ui-shadow) !important; }
    [data-testid="stChatInput"] textarea { color:var(--ui-text) !important; background:transparent !important; }
    [data-testid="stDataFrame"] { border:1px solid var(--ui-border); border-radius:14px; overflow:hidden; box-shadow:0 8px 24px color-mix(in srgb, var(--ui-text) 7%, transparent); }

    .premium-panel { background:var(--ui-surface); border:1px solid var(--ui-border); border-radius:18px; padding:1rem 1.1rem; box-shadow:var(--ui-shadow); animation:uiFadeUp .42s ease both; }
    .premium-kicker { text-transform:uppercase; letter-spacing:.14em; font-size:.72rem; font-weight:800; color:var(--ui-accent); }
    .premium-chip { display:inline-flex; align-items:center; gap:.4rem; border:1px solid var(--ui-border); background:var(--ui-tint); color:var(--ui-text); border-radius:999px; padding:.35rem .65rem; font-size:.78rem; font-weight:700; margin:.15rem .25rem .15rem 0; }
    .premium-muted { color:var(--ui-muted); }
    @keyframes uiFadeUp { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
    @media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation:none !important; transition:none !important; } }
    @media (max-width: 900px) { .block-container { padding-left:1rem; padding-right:1rem; } }
    </style>
    """
    # ``st.html`` is not iframed, so these CSS variables track Streamlit's
    # live theme tokens as Settings changes between Light/Dark/System.
    st.html(css)
