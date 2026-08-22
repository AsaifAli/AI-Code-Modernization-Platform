"""Streamlit UI for the standalone agent_service — upload a project, run an
AI-assisted migration, and watch it happen."""
from __future__ import annotations

import os
import json
import html
import time
import uuid
from pathlib import Path

import requests
import streamlit as st

from api_client import AgentServiceClient, ApiError, DEFAULT_BASE_URL
from sidebar_toggle import render_sidebar_toggle

# --------------------------------------------------------------------------
# Page config & constants
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Code Migration Studio",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Shared premium visual layer (presentation-only).
from ui_theme import apply_theme
apply_theme()
render_sidebar_toggle()


LOADING_LOTTIE_URL = "https://assets9.lottiefiles.com/packages/lf20_usmfx6bp.json"
THINKING_LOTTIE_URL = "https://assets1.lottiefiles.com/packages/lf20_khzniaya.json"
EMPTY_LOTTIE_URL = "https://assets1.lottiefiles.com/packages/lf20_wnqlfojb.json"

TARGET_LANGUAGES = [
    "", "python", "java", "javascript", "typescript", "csharp", "go", "kotlin", "php", "ruby",
]

# --------------------------------------------------------------------------
# Styling
# --------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .hero {
        position: relative;
        overflow: hidden;
        border-radius: 22px;
        padding: 2.2rem 2.3rem 2rem;
        margin-bottom: 1.2rem;
        background: linear-gradient(135deg, var(--ui-hero-start) 0%, var(--ui-hero-mid) 48%, var(--ui-hero-end) 100%);
        color: var(--ui-hero-text);
        border: 1px solid var(--ui-hero-border);
        box-shadow: 0 18px 50px rgba(15,23,42,.18);
    }
    .hero::after {
        content:"";
        position:absolute; width:360px; height:360px; right:-110px; top:-160px;
        background:radial-gradient(circle, var(--ui-hero-glow), transparent 68%);
        pointer-events:none;
    }
    .hero h1 { position:relative; z-index:1; font-weight:850; font-size:2.45rem; letter-spacing:-.04em; margin:0 0 .45rem; }
    .hero p { position:relative; z-index:1; font-size:1.04rem; color:var(--ui-hero-muted); max-width:760px; margin:0; line-height:1.6; }
    .hero-kicker { position:relative; z-index:1; font-size:.72rem; letter-spacing:.16em; text-transform:uppercase; font-weight:800; color:var(--ui-accent); margin-bottom:.55rem; }
    .hero-chips { position:relative; z-index:1; display:flex; flex-wrap:wrap; gap:.45rem; margin-top:1.15rem; }
    .hero-chip { display:inline-flex; align-items:center; gap:.4rem; padding:.34rem .68rem; border-radius:999px; border:1px solid var(--ui-hero-chip-border); background:var(--ui-hero-chip-bg); color:var(--ui-hero-text); font-size:.76rem; font-weight:700; }
    .status-dot { display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:7px; }
    .status-dot.online { background:#22c55e; box-shadow:0 0 0 4px rgba(34,197,94,.12); }
    .status-dot.offline { background:#ef4444; box-shadow:0 0 0 4px rgba(239,68,68,.10); }
    .status-dot.checking { background:#94a3b8; animation:pulse 1.2s infinite; }
    @keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(148,163,184,.55)} 70%{box-shadow:0 0 0 8px rgba(148,163,184,0)} 100%{box-shadow:0 0 0 0 rgba(148,163,184,0)} }

    .workbench-panel { background:var(--ui-surface); border:1px solid var(--ui-border); border-radius:18px; padding:1.05rem 1.15rem; box-shadow:var(--ui-shadow); }
    .panel-kicker { text-transform:uppercase; letter-spacing:.14em; font-size:.7rem; font-weight:850; color:var(--ui-accent); margin-bottom:.35rem; }
    .panel-title { font-size:1.05rem; font-weight:800; color:var(--ui-text); margin-bottom:.15rem; }
    .panel-subtitle { font-size:.88rem; color:var(--ui-muted); line-height:1.5; }
    .step-row { display:grid; grid-template-columns:2rem 1fr; gap:.75rem; align-items:start; padding:.78rem 0; border-top:1px solid var(--ui-border); }
    .step-row:first-of-type { border-top:none; padding-top:.2rem; }
    .step-no { width:2rem; height:2rem; display:flex; align-items:center; justify-content:center; border-radius:9px; font-size:.72rem; font-weight:850; background:var(--ui-tint); color:var(--ui-accent); border:1px solid var(--ui-border); }
    .step-title { font-weight:760; color:var(--ui-text); font-size:.92rem; }
    .step-copy { font-size:.78rem; color:var(--ui-muted); margin-top:.15rem; line-height:1.45; }
    .metric-strip { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:.75rem; margin:.8rem 0 1.15rem; }
    .metric-card { background:var(--ui-surface); border:1px solid var(--ui-border); border-radius:16px; padding:.85rem .9rem; box-shadow:var(--ui-shadow); }
    .metric-label { color:var(--ui-faint); font-size:.72rem; font-weight:750; text-transform:uppercase; letter-spacing:.09em; }
    .metric-value { color:var(--ui-text); font-size:1.25rem; font-weight:850; margin-top:.18rem; }
    .soft-note { border:1px solid var(--ui-border); background:var(--ui-surface-2); border-radius:14px; padding:.75rem .85rem; color:var(--ui-muted); font-size:.8rem; line-height:1.5; }
    .state-card { border:1px solid var(--ui-border); background:linear-gradient(135deg,var(--ui-surface),var(--ui-surface-2)); border-radius:18px; padding:1rem 1.1rem; box-shadow:var(--ui-shadow); }
    .state-title { font-weight:820; color:var(--ui-text); font-size:1rem; }
    .state-copy { color:var(--ui-muted); font-size:.83rem; line-height:1.5; margin-top:.15rem; }
    .completion-card { border:1px solid rgba(34,197,94,.28); background:linear-gradient(135deg,rgba(34,197,94,.08),var(--ui-surface)); border-radius:16px; padding:1rem 1.1rem; margin:.8rem 0 1rem; }
    .completion-title { font-size:1rem; font-weight:820; color:var(--ui-success); }
    .completion-subtitle { margin-top:.2rem; color:var(--ui-muted); font-size:.84rem; }
    .glass-card { background:var(--ui-surface); border:1px solid var(--ui-border); border-radius:16px; padding:1rem 1.1rem; margin-bottom:.75rem; box-shadow:var(--ui-shadow); }
    .fade-in { animation:uiFadeUp .4s ease both; }
    @keyframes uiFadeUp { from {opacity:0; transform:translateY(6px)} to {opacity:1; transform:none} }
    @media (max-width: 900px) { .metric-strip { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media (prefers-reduced-motion: reduce) { *,*::before,*::after { animation:none !important; transition:none !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
if "base_url" not in st.session_state:
    st.session_state.base_url = DEFAULT_BASE_URL
if "llm_gateway_session_token" not in st.session_state:
    st.session_state.llm_gateway_session_token = ""

portfolio_token = str(st.query_params.get("portfolio_llm_session", "")).strip()
if portfolio_token:
    st.session_state.llm_gateway_session_token = portfolio_token
    try:
        del st.query_params["portfolio_llm_session"]
    except Exception:
        pass
if "token" not in st.session_state:
    st.session_state.token = "streamlit-user"
if "active_task_id" not in st.session_state:
    st.session_state.active_task_id = None
if "active_migration_name" not in st.session_state:
    st.session_state.active_migration_name = None
if "active_task_started_at" not in st.session_state:
    st.session_state.active_task_started_at = None
if "last_progress" not in st.session_state:
    st.session_state.last_progress = {}
if "active_section_widget" not in st.session_state:
    st.session_state.active_section_widget = "New Migration"


def get_client() -> AgentServiceClient:
    return AgentServiceClient(base_url=st.session_state.base_url, token=st.session_state.token, gateway_token=st.session_state.get("llm_gateway_session_token", ""))


def try_lottie(url: str, height: int = 160):
    """Best-effort Lottie animation; silently falls back to nothing if unavailable."""
    try:
        from streamlit_lottie import st_lottie
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            st_lottie(resp.json(), height=height, key=str(uuid.uuid4()))
            return True
    except Exception:
        pass
    return False


def typewriter(text: str, speed: float = 0.012):
    """Reveal text character-by-character for a live 'typing' feel."""
    placeholder = st.empty()
    shown = ""
    step = max(1, len(text) // 200)  # cap total redraws for long answers
    for i in range(0, len(text), step):
        shown = text[: i + step]
        placeholder.markdown(f'<div class="glass-card">{shown}▌</div>', unsafe_allow_html=True)
        time.sleep(speed)
    placeholder.markdown(f'<div class="glass-card fade-in">{text}</div>', unsafe_allow_html=True)


def _as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _release_readiness(migration_name: str, completed_payload: dict) -> dict:
    """Build a factual release-readiness summary from persisted backend evidence."""
    cache_key = f"release_readiness::{migration_name}"
    cached = st.session_state.get(cache_key)
    if isinstance(cached, dict):
        return cached
    result = {
        "release_gate": bool(completed_payload.get("release_ready", False)),
        "semantic_status": "not_available",
        "security_status": "not_available",
        "security_critical": 0,
        "verification_score": None,
        "confidence": "Review",
    }
    try:
        semantic = client.semantic_verification(migration_name).get("data", {})
        result["semantic_status"] = str(semantic.get("status", "not_available"))
        result["verification_score"] = semantic.get("score")
    except ApiError:
        pass
    try:
        evidence = client.migration_evidence(migration_name).get("data", {})
        security = evidence.get("security_review", {}) or {}
        result["security_status"] = str(security.get("status", "not_available"))
        result["security_critical"] = int(security.get("critical", 0) or 0)
    except (ApiError, TypeError, ValueError):
        pass

    if (
        result["release_gate"]
        and result["semantic_status"] == "verified"
        and result["security_status"] == "passed"
        and result["security_critical"] == 0
    ):
        result["confidence"] = "High"
    elif result["semantic_status"] in {"verified", "partial"} and result["security_status"] in {"passed", "review"}:
        result["confidence"] = "Moderate"
    st.session_state[cache_key] = result
    return result


def render_release_readiness(migration_name: str, completed_payload: dict) -> None:
    """Render a compact, data-backed release readiness card."""
    readiness = _release_readiness(migration_name, completed_payload)
    gate_label = "PASS" if readiness["release_gate"] else "BLOCKED"
    gate_icon = "✓" if readiness["release_gate"] else "!"
    st.markdown(
        '<div class="release-grid">'
        f'<div class="release-card"><div class="release-label">Release readiness</div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:.8rem;margin:.2rem 0 .45rem">'
        f'<div class="release-score">{readiness["confidence"]}</div>'
        f'<div class="release-status">{gate_icon} Release gate · {gate_label}</div></div>'
        f'<div class="change-copy">Semantic verification: <b>{readiness["semantic_status"].replace("_", " ").title()}</b> · Security review: <b>{readiness["security_status"].replace("_", " ").title()}</b></div></div>'
        f'<div class="release-card"><div class="release-label">Evidence snapshot</div>'
        f'<div class="delta-row"><span class="delta-label">Verification score</span><span class="delta-value">{readiness["verification_score"] if readiness["verification_score"] is not None else "—"}</span></div>'
        f'<div class="delta-row"><span class="delta-label">Critical security findings</span><span class="delta-value">{readiness["security_critical"]}</span></div>'
        f'<div class="delta-row"><span class="delta-label">Next action</span><span class="delta-value">{"Review & release" if readiness["release_gate"] else "Resolve release blockers"}</span></div></div>'
        '</div>',
        unsafe_allow_html=True,
    )


def render_change_explorer(migration_name: str) -> None:
    """Show a before/after modernization snapshot using real comparison-report data."""
    cache_key = f"change_report::{migration_name}"
    report = st.session_state.get(cache_key)
    if not isinstance(report, dict):
        try:
            report = client.report(migration_name, persist=False, include_markdown=False, require_migrated=True)
            st.session_state[cache_key] = report
        except ApiError:
            st.info("Comparison evidence becomes available after the migration report is ready.")
            return

    if report.get("status") != "ready":
        st.info(report.get("message", "Comparison report is not ready yet."))
        return

    cards = report.get("module_review_cards") or []
    mode = report.get("analysis_mode", "unknown")
    st.markdown('<div class="panel-kicker">CODE CHANGE EXPLORER</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Before → after modernization snapshot</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-subtitle">A concise comparison built from the persisted migration report — no simulated diff counts.</div>', unsafe_allow_html=True)

    if mode == "source_vs_migrated":
        total_files = 0
        total_functions_delta = 0
        total_loc_delta = 0
        total_dep_delta = 0
        measurable = 0
        for card in cards:
            delta = card.get("what_changed", {}).get("semantic_delta", {}) or {}
            if delta.get("function_delta") is not None:
                total_functions_delta += int(delta.get("function_delta") or 0)
                total_loc_delta += int(delta.get("loc_delta") or 0)
                total_dep_delta += int(delta.get("dependency_delta") or 0)
                measurable += 1
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Modules compared", len(cards))
        m2.metric("Function delta", f"{total_functions_delta:+d}" if measurable else "—")
        m3.metric("LOC delta", f"{total_loc_delta:+d}" if measurable else "—")
        m4.metric("Dependency delta", f"{total_dep_delta:+d}" if measurable else "—")

        preview = cards[:3]
        for card in preview:
            change = card.get("what_changed", {}) or {}
            delta = change.get("semantic_delta", {}) or {}
            module = card.get("module", "module")
            pattern = change.get("legacy_to_modern_pattern", "Comparison available")
            left_copy = f"Legacy pattern: {pattern}"
            right_copy = "; ".join(change.get("key_transformations", [])[:2]) or "Modernized structure recorded in the migration report."
            st.markdown(
                '<div class="change-grid">'
                f'<div class="change-card before"><div class="change-title">Before · {html.escape(str(module))}</div><div class="change-copy">{html.escape(str(left_copy))}</div></div>'
                f'<div class="change-card after"><div class="change-title">After · {html.escape(str(module))}</div><div class="change-copy">{html.escape(str(right_copy))}</div>'
                f'<div class="delta-row"><span class="delta-label">Functions</span><span class="delta-value">{delta.get("function_delta", "—")}</span></div>'
                f'<div class="delta-row"><span class="delta-label">LOC</span><span class="delta-value">{delta.get("loc_delta", "—")}</span></div>'
                f'<div class="delta-row"><span class="delta-label">Dependencies</span><span class="delta-value">{delta.get("dependency_delta", "—")}</span></div></div>'
                '</div>',
                unsafe_allow_html=True,
            )
    else:
        # Migrated-only mode: be explicit rather than pretending to have a source diff.
        st.warning("Source baseline comparison is not available for this migration, so the explorer is showing migrated-code evidence only.")
        for card in cards[:4]:
            st.markdown(
                f'<div class="change-card after"><div class="change-title">{html.escape(str(card.get("module", "module")))}</div>'
                f'<div class="change-copy">{html.escape(str(card.get("reason", "Review the module-level risk profile.")))}</div></div>',
                unsafe_allow_html=True,
            )


def render_codebase_answer(migration_name: str, answer: dict, is_target: bool) -> None:
    """Render an answer with lightweight evidence metadata, not hidden reasoning."""
    route = "Target code" if is_target else "Source code"
    st.markdown(
        f'<div class="release-status">⌁ Route · {route}</div>',
        unsafe_allow_html=True,
    )
    typewriter(answer.get("answer", ""))
    st.caption("Evidence is grounded in the selected migration knowledge base; internal reasoning is not exposed.")


# The backend now streams Agno Workflow step events into the task status API.
# This UI renders those persisted events; it is no longer a time-based approximation.
PIPELINE_STAGES = [
    ("🔍", "Scan source"), ("🛡️", "Verify scan"), ("🧠", "Build knowledge base"),
    ("🗺️", "Plan migration"), ("🛡️", "Verify plan"), ("🔄", "Convert code"),
    ("🧪", "Post-migration engineering"),
]

def render_live_plan(progress: dict):
    """Render a single car-style tachometer from persisted workflow progress."""
    plan = progress.get("plan") or []
    if not plan:
        # Older task payloads may only have stage/percent. Still render the tachometer.
        percent = int(progress.get("percent") or 0)
        stage = str(progress.get("stage") or "workflow")
        stage_map = {
            "planning": "Migration planning",
            "knowledge_base": "Building knowledge base",
            "conversion": "Converting code",
            "engineering": "Post-migration engineering",
            "analysis": "Analyzing migration",
            "security": "Security verification",
            "workflow": "Executing migration workflow",
            "completed": "Migration complete",
        }
        label = stage_map.get(stage, stage.replace("_", " ").title())
        completed = int(round(percent / 100 * len(PIPELINE_STAGES)))
        total = len(PIPELINE_STAGES)
        message = str(progress.get("message", "Executing migration workflow"))
    else:
        total = len(plan)
        completed = sum(1 for x in plan if x.get("status") == "complete")
        running_index = next((i for i, x in enumerate(plan) if x.get("status") in {"running", "in_progress"}), None)
        percent = 100 if completed == total else int(((running_index if running_index is not None else completed) / total) * 100)
        current = next((x.get("name") for x in plan if x.get("status") in {"running", "in_progress"}), None)
        label = current or ("Migration complete" if percent >= 100 else "Preparing migration")
        message = str(progress.get("message", "Executing migration workflow"))

    percent = max(0, min(100, percent))
    # Tachometer sweep: -92deg = far-left idle, +88deg = far-right redline.
    angle = -92 + (percent * 1.80)

    ticks = []
    for i in range(11):
        deg = -90 + (i * 18)
        major = " major" if i % 2 == 0 else ""
        ticks.append(f'<span class="tick{major}" style="transform:translateX(-50%) rotate({deg}deg)"></span>')

    html = (
        '<div class="gauge-wrap">'
        '<div class="tachometer">'
        '<div class="tachometer-face">'
        '<div class="tachometer-arc"></div>'
        + ''.join(ticks) +
        f'<div class="tachometer-needle" style="--needle-angle:{angle}deg;"></div>'
        '<div class="tachometer-hub"></div>'
        '<div class="tachometer-center">'
        f'<div class="gauge-value">{percent}%</div>'
        '<div class="gauge-unit">Migration Load</div>'
        '</div>'
        '</div>'
        '</div>'
        f'<div class="gauge-label">{completed}/{total} stages complete</div>'
        f'<div class="gauge-message">{label}</div>'
        f'<div class="gauge-label">{message}</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def skeleton_lines(n: int = 3, heights=("1.4rem", "1rem", "1rem")):
    """Render shimmering skeleton bars as a loading placeholder."""
    bars = "".join(
        f'<div class="skeleton" style="height:{h}; margin-bottom:0.5rem; width:{95 - i*8}%;"></div>'
        for i, h in enumerate((heights * n)[:n])
    )
    st.markdown(bars, unsafe_allow_html=True)


def count_up(label: str, target: int, duration: float = 0.5, steps: int = 12):
    """Animate a metric counting up from 0 to target."""
    placeholder = st.empty()
    if target <= 0:
        placeholder.metric(label, target)
        return
    step_count = min(steps, target) or 1
    for i in range(1, step_count + 1):
        value = round(target * i / step_count)
        placeholder.metric(label, value)
        time.sleep(duration / step_count)
    placeholder.metric(label, target)


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### LegacyLens")
    st.caption("AI Code Migration Studio")
    st.markdown('<div class="soft-note">🧩 Developer workbench · evidence-first modernization</div>', unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("**Connection**")
    st.session_state.base_url = st.text_input("agent_service URL", st.session_state.base_url)
    st.session_state.token = st.text_input(
        "Identity token",
        st.session_state.token,
        help=(
            "agent_service uses this stable bearer identity to scope which migrations you can see."
        ),
    )
    client = get_client()
    try:
        health = client.health()
        online = str(health.get("status", "")).lower() in ("ok", "healthy")
    except ApiError:
        online = False
    dot_class = "online" if online else "offline"
    label = "Connected" if online else "Unreachable"
    st.markdown(f'<span class="status-dot {dot_class}"></span><strong>{label}</strong>', unsafe_allow_html=True)
    if online:
        st.caption("agent_service is responding")
    else:
        st.caption("Check the URL and agent_service status.")
    st.markdown("---")
    st.markdown("**Current migration**")
    st.markdown(f"`{st.session_state.get('active_migration_name') or 'None'}`")
    if st.session_state.get("active_task_id"):
        st.caption(f"Task · {st.session_state.active_task_id}")
    st.markdown("---")
    st.markdown("**Workflow**")
    for idx, (_, name) in enumerate(PIPELINE_STAGES, start=1):
        st.caption(f"{idx:02d}  {name}")

# --------------------------------------------------------------------------
# Product shell
# --------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero fade-in">
      <div class="hero-kicker">AI-assisted developer workbench</div>
      <h1>Modernize legacy code with evidence, not guesswork.</h1>
      <p>Scan a codebase, build a migration plan, convert it with an agent team, and verify the result before release — with traceable workflow evidence at every stage.</p>
      <div class="hero-chips">
        <span class="hero-chip">🧭 Dependency-aware planning</span>
        <span class="hero-chip">🧪 Behavioral verification</span>
        <span class="hero-chip">🛡️ Release gates</span>
        <span class="hero-chip">📦 Downloadable artifact</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

SECTIONS = [
    "New Migration",
    "My Migrations",
    "Architecture & Analysis",
    "Semantic Verification",
    "Ask the Codebase",
    "About",
]
active_section = st.segmented_control(
    "Migration sections",
    SECTIONS,
    key="active_section_widget",
    selection_mode="single",
    label_visibility="collapsed",
)

st.markdown(
    '<div class="metric-strip">'
    '<div class="metric-card"><div class="metric-label">Workflow</div><div class="metric-value">7 stages</div></div>'
    '<div class="metric-card"><div class="metric-label">Verification</div><div class="metric-value">Behavioral</div></div>'
    '<div class="metric-card"><div class="metric-label">Release gate</div><div class="metric-value">Enabled</div></div>'
    f'<div class="metric-card"><div class="metric-label">Active migration</div><div class="metric-value">{st.session_state.get("active_migration_name") or "None"}</div></div>'
    '</div>',
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Tab: New Migration
# --------------------------------------------------------------------------
if active_section == "New Migration":
    left, right = st.columns([1.3, 1], gap="large")

    with left:
        st.markdown('<div class="panel-kicker">01 · SOURCE</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">Bring the codebase into the workbench</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-subtitle">Upload the source project and optionally provide an existing target project for comparison-aware migrations.</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:.55rem"></div>', unsafe_allow_html=True)
        source_zip = st.file_uploader("Source project archive", type=["zip"], key="source_zip")
        target_zip = st.file_uploader("Optional target archive", type=["zip"], key="target_zip")
        st.markdown('<div class="soft-note">🔒 Uploaded archives are passed to the migration service workspace. The UI does not inspect or rewrite project contents client-side.</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:1.0rem"></div><div class="panel-kicker">02 · INTENT</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">Describe the modernization objective</div>', unsafe_allow_html=True)
        migration_name = st.text_input("Migration name", placeholder="e.g. billing-service-to-fastapi")
        description = st.text_area(
            "Migration brief",
            placeholder="Migrate this Java Spring service to a Python FastAPI microservice, keeping the existing REST contract...",
            height=125,
        )
        col_a, col_b = st.columns(2)
        with col_a:
            target_language = st.selectbox("Target language", TARGET_LANGUAGES)
        with col_b:
            github_token = st.text_input("GitHub token (optional)", type="password")

        launch = st.button("Launch migration", type="primary", width="stretch")
        st.caption("The agent team will scan → verify → plan → convert → engineer → gate the release.")

        if launch:
            if not source_zip:
                st.warning("Please upload a source project archive first.")
            elif not migration_name or not description:
                st.warning("Migration name and description are required.")
            else:
                try:
                    with st.spinner("Uploading project to the migration service..."):
                        upload_result = client.upload_team_files(
                            migration_name=migration_name,
                            source_bytes=source_zip.getvalue(),
                            source_filename=source_zip.name,
                            target_bytes=target_zip.getvalue() if target_zip else None,
                            target_filename=target_zip.name if target_zip else None,
                        )
                    with st.spinner("Queuing the agent team..."):
                        result = client.run_team(
                            source_path=upload_result["source_path"],
                            migration_name=migration_name,
                            description=description,
                            target_language=target_language or None,
                            target_path=upload_result.get("target_path"),
                            github_token=github_token or None,
                        )
                    st.session_state.active_task_id = result["task_id"]
                    st.session_state.active_migration_name = migration_name
                    st.session_state.active_task_started_at = time.time()
                    st.session_state.completion_toast_shown = False
                    st.session_state.pop(f"release_readiness::{migration_name}", None)
                    st.session_state.pop(f"change_report::{migration_name}", None)
                    st.session_state.last_progress = {"stage": "workflow", "percent": 2, "message": "Preparing workflow telemetry"}
                    st.toast(f"Migration '{migration_name}' queued")
                    st.success(f"Migration queued · `{result['task_id']}`")
                    detected = {
                        k.replace("detected_", "").replace("_", " ").title(): v
                        for k, v in result.items()
                        if k.startswith("detected_") and v not in (None, False, "")
                    }
                    if detected:
                        with st.expander("Detected stack", expanded=False):
                            st.json(detected, expanded=False)
                except ApiError as e:
                    st.error(f"Failed to launch migration: {e.detail}")

    with right:
        st.markdown('<div class="panel-kicker">03 · LIVE WORKFLOW</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">Migration control room</div>', unsafe_allow_html=True)
        st.markdown('<div class="panel-subtitle">Live progress is read from persisted workflow events, not simulated timers.</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:.45rem"></div>', unsafe_allow_html=True)
        if not st.session_state.active_task_id:
            st.markdown(
                '<div class="state-card"><div class="state-title">Ready for a migration</div><div class="state-copy">Launch a project to watch the seven-stage engineering pipeline execute here.</div></div>',
                unsafe_allow_html=True,
            )
            for i, (icon, name) in enumerate(PIPELINE_STAGES, start=1):
                st.markdown(
                    f'<div class="step-row"><div class="step-no">{i:02d}</div><div><div class="step-title">{icon} {name}</div><div class="step-copy">Evidence is persisted so completed runs can be reviewed later.</div></div></div>',
                    unsafe_allow_html=True,
                )
        else:
            placeholder = st.empty()
            auto_refresh = st.checkbox("Auto-refresh every 4s", value=True)
            try:
                status = client.task_status(st.session_state.active_task_id)
            except ApiError as e:
                status = {"status": "unknown", "error": e.detail}

            state = str(status.get("status", "unknown")).lower()
            badge_class = {
                "running": "running", "queued": "running", "accepted": "running",
                "completed": "completed", "success": "completed",
                "failed": "failed", "error": "failed",
            }.get(state, "running")

            with placeholder:
                st.markdown(
                    f'<div class="state-card"><div class="state-title"><span class="badge {badge_class}">{state.upper()}</span> &nbsp; {st.session_state.get("active_migration_name") or "Migration"}</div>'
                    f'<div class="state-copy">Task · <code>{st.session_state.active_task_id}</code></div></div>',
                    unsafe_allow_html=True,
                )
                if badge_class == "running":
                    raw_progress = status.get("result")
                    progress = {}
                    if isinstance(raw_progress, dict):
                        progress = raw_progress
                    elif isinstance(raw_progress, str):
                        try:
                            parsed = json.loads(raw_progress)
                            if isinstance(parsed, dict) and parsed.get("kind") == "progress":
                                progress = parsed
                        except Exception:
                            pass
                    progress = progress or st.session_state.get("last_progress") or {"stage": "workflow", "percent": 2, "message": "Preparing workflow telemetry"}
                    st.session_state.last_progress = progress
                    render_live_plan(progress)
                elif badge_class == "completed":
                    if not st.session_state.get("completion_toast_shown"):
                        st.toast("Migration completed", icon="✓")
                        st.session_state.completion_toast_shown = True
                    st.markdown('<div class="completion-card"><div class="completion-title">Release candidate ready</div><div class="completion-subtitle">The workflow reached a terminal state. Review verification evidence before downloading the artifact.</div></div>', unsafe_allow_html=True)
                    raw_completed = status.get("result")
                    completed_payload = {}
                    if isinstance(raw_completed, str):
                        try:
                            parsed_completed = json.loads(raw_completed)
                            if isinstance(parsed_completed, dict) and parsed_completed.get("kind") == "completed":
                                completed_payload = parsed_completed
                        except Exception:
                            pass
                    terminal_progress = st.session_state.get("last_progress") or {"stage": "completed", "percent": 100, "message": "Migration complete"}
                    if completed_payload.get("plan"):
                        terminal_progress = {"plan": completed_payload["plan"], "percent": 100, "message": "All migration stages completed"}
                    else:
                        terminal_progress = dict(terminal_progress)
                        terminal_progress.update({"percent": 100, "stage": "completed", "message": "All migration stages completed"})
                    st.session_state.last_progress = terminal_progress
                    render_live_plan(terminal_progress)
                    if st.session_state.active_migration_name and completed_payload.get("release_ready", True):
                        try:
                            data = client.download_migration(st.session_state.active_migration_name)
                            st.download_button("Download release artifact", data=data, file_name=f"{st.session_state.active_migration_name}.zip", mime="application/zip", width="stretch")
                        except ApiError:
                            st.caption("Download will be available shortly.")
                    if st.session_state.active_migration_name:
                        render_release_readiness(st.session_state.active_migration_name, completed_payload)
                        render_change_explorer(st.session_state.active_migration_name)
                    st.info("Next: inspect Architecture & Analysis, Semantic Verification, or Ask the Codebase.")
                elif badge_class == "failed":
                    raw_failed = status.get("result")
                    failed_payload = {}
                    if isinstance(raw_failed, str):
                        try:
                            parsed_failed = json.loads(raw_failed)
                            if isinstance(parsed_failed, dict):
                                failed_payload = parsed_failed
                        except Exception:
                            pass
                    output_message = failed_payload.get("message") or status.get("error") or "Migration did not pass the release gate."
                    terminal_progress = st.session_state.get("last_progress") or {"stage": "workflow", "percent": 0, "message": "Migration stopped"}
                    if failed_payload.get("plan"):
                        terminal_progress = {"plan": failed_payload["plan"], "message": str(output_message)}
                    else:
                        terminal_progress = dict(terminal_progress)
                        terminal_progress["message"] = str(output_message)
                    st.session_state.last_progress = terminal_progress
                    render_live_plan(terminal_progress)
                    if failed_payload.get("kind") == "blocked" or "release gate" in str(output_message).lower():
                        if st.session_state.active_migration_name:
                            try:
                                data = client.download_migration(st.session_state.active_migration_name)
                                st.download_button("Download gated artifact", data=data, file_name=f"{st.session_state.active_migration_name}.zip", mime="application/zip", width="stretch", key="blocked_demo_download")
                            except ApiError:
                                st.caption("Download will be available shortly.")
                    else:
                        st.error(f"Migration failed: {output_message}")

                if status.get("result"):
                    with st.expander("Workflow payload", expanded=False):
                        st.write(status["result"])

            if auto_refresh and badge_class == "running":
                time.sleep(4)
                st.rerun()

# --------------------------------------------------------------------------
# Tab: My Migrations
# --------------------------------------------------------------------------
if active_section == "My Migrations":
    st.markdown("#### Your migrations")
    if st.button("Refresh list"):
        st.rerun()

    list_placeholder = st.empty()
    with list_placeholder.container():
        skeleton_lines(3)
    try:
        payload = client.list_migrations()
        migrations = payload.get("migrations", [])
    except ApiError as e:
        migrations = []
        st.error(f"Could not load migrations: {e.detail}")
    list_placeholder.empty()

    if migrations:
        count_up("Migrations found", len(migrations))

    if not migrations:
        try_lottie(EMPTY_LOTTIE_URL, height=200)
        st.caption("No migrations yet — start one from the **New Migration** tab.")
    else:
        status_icons = {"complete": "✅", "in_progress": "⏳", "failed": "❌"}
        for m in migrations:
            if isinstance(m, str):
                m = {"migration_name": m, "status": ""}
            elif not isinstance(m, dict):
                m = {"migration_name": str(m), "status": ""}
            name = m.get("migration_name") or m.get("name") or str(m)
            icon = status_icons.get(str(m.get("status", "")).lower(), "")
            with st.expander(f"{icon} {name}".strip(), expanded=False):
                st.markdown('<div class="glass-card fade-in">', unsafe_allow_html=True)
                cols = st.columns(3)
                if cols[0].button("Status", key=f"status_{name}"):
                    try:
                        st.json(client.migration_status(name))
                    except ApiError as e:
                        st.error(e.detail)
                if cols[1].button("Download", key=f"dl_{name}"):
                    try:
                        data = client.download_migration(name)
                        st.toast(f"'{name}' ready to save")
                        st.download_button(
                            "Save zip (demo artifact)", data=data, file_name=f"{name}.zip",
                            mime="application/zip", key=f"dlbtn_{name}",
                        )
                    except ApiError as e:
                        st.error(e.detail)
                if cols[2].button("Delete", key=f"del_{name}"):
                    try:
                        client.delete_migration(name)
                        st.toast(f"Deleted '{name}'")
                        st.success(f"Deleted '{name}'")
                        st.rerun()
                    except ApiError as e:
                        st.error(e.detail)
                st.markdown("</div>", unsafe_allow_html=True)

# --------------------------------------------------------------------------
# Tab: Architecture & Analysis
# --------------------------------------------------------------------------
if active_section == "Architecture & Analysis":
    st.markdown("#### Migrated code intelligence")
    analysis_name = st.text_input("Migration name", value=st.session_state.active_migration_name or "", key="analysis_migration")
    if analysis_name:
        try:
            payload = client.migrated_analysis(analysis_name)
            data = payload.get("data", {})
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Files", data.get("file_count", 0))
            c2.metric("Modules", len(data.get("modules", [])))
            c3.metric("Languages", len(data.get("languages", {})))
            c4.metric("Architecture", data.get("architecture_style", "Unknown"))

            st.markdown("### Architecture at a glance")
            st.info(data.get("summary", "No architecture summary available."))

            # Render the inferred module graph using Streamlit's native Graphviz support.
            dot = ["digraph G {", "rankdir=LR;", "node [shape=box, style=rounded];"]
            modules = {m.get("name"): m for m in data.get("modules", [])}
            for name, module in modules.items():
                safe = name.replace('"', '\\"')
                dot.append(f'"{safe}" [label="{safe}\n{module.get("files", 0)} files"];')
            for edge in data.get("dependency_edges", []):
                dot.append(f'"{edge.get("from", "")}" -> "{edge.get("to", "")}";')
            dot.append("}")
            try:
                st.graphviz_chart("\n".join(dot), width="stretch")
            except Exception:
                st.code(data.get("diagram_mermaid", ""), language="mermaid")

            st.markdown("### Technology profile")
            for lang, count in sorted(data.get("languages", {}).items(), key=lambda x: (-x[1], x[0])):
                st.write(f"**{lang}** — {count} files")

            st.markdown("### Generated architecture README")
            readme_path = None
            # The API intentionally returns structured data; the UI presents a README-style narrative from it.
            st.markdown(f"**Architecture style:** {data.get('architecture_style', 'Unknown')}")
            st.markdown("**Layers detected:**")
            for layer, members in data.get("layers", {}).items():
                st.write(f"- **{layer}:** {', '.join(members) if members else 'None'}")

            with st.expander("Static-analysis limitations"):
                for limitation in data.get("limitations", []):
                    st.write(f"- {limitation}")
        except ApiError as e:
            st.info("Architecture analysis becomes available after the post-migration engineering stage completes.")
    else:
        st.caption("Complete a migration, then enter its name here to inspect the generated architecture.")

# --------------------------------------------------------------------------
# Tab: Semantic Verification
# --------------------------------------------------------------------------
if active_section == "Semantic Verification":
    st.markdown("#### Semantic & behavioral verification")
    semantic_name = st.text_input("Migration name", value=st.session_state.active_migration_name or "", key="semantic_migration")
    if semantic_name:
        try:
            payload = client.semantic_verification(semantic_name)
            data = payload.get("data", {})
            status = data.get("status", "not_available")
            score = data.get("score")
            contract = data.get("contract", {})
            execution = data.get("execution", {})
            tests = data.get("test_evidence", {})
            probes = data.get("behavioral_probes", {})

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Verification", status.replace("_", " ").title())
            c2.metric("Evidence score", f"{score}/100" if score is not None else "N/A")
            c3.metric("Contract coverage", f"{contract.get('coverage_percent', 0)}%" if contract.get('coverage_percent') is not None else "N/A")
            c4.metric("Test files", tests.get("count", 0))
            c5.metric("Probe coverage", f"{probes.get('coverage_percent', 0)}%" if probes.get('coverage_percent') is not None else "N/A")

            if status == "verified":
                st.success("Migration has strong contract evidence and target test evidence.")
            elif status == "partial":
                st.warning("Migration has partial semantic evidence. Review the missing or incompatible contracts before release.")
            else:
                st.info("Semantic evidence is not available yet; run post-migration analysis first.")

            st.markdown("### Source → target contract coverage")
            cols = st.columns(4)
            cols[0].metric("Source public symbols", contract.get("source_symbols", 0))
            cols[1].metric("Target symbols", contract.get("target_symbols", 0))
            cols[2].metric("Matched", contract.get("matched", 0))
            cols[3].metric("Missing / incompatible", contract.get("missing", 0) + contract.get("arity_incompatible", 0))

            missing = contract.get("missing_symbols", [])
            incompatible = contract.get("incompatible", [])
            if missing:
                with st.expander(f"Missing target symbols ({len(missing)})"):
                    for item in missing:
                        st.write(f"- **{item.get('name')}** — `{item.get('file')}` line {item.get('line')}")
            if incompatible:
                with st.expander(f"Signature / arity mismatches ({len(incompatible)})"):
                    for item in incompatible:
                        st.write(f"- **{item.get('source', {}).get('name')}**: source arity {item.get('source', {}).get('arity')} → target arity {item.get('target', {}).get('arity')}")

            st.markdown("### Source → target behavioral probes")
            pc1, pc2, pc3, pc4 = st.columns(4)
            pc1.metric("Selected functions", probes.get("selected", 0))
            pc2.metric("Executed cases", probes.get("cases", 0))
            pc3.metric("Passed", probes.get("passed", 0))
            pc4.metric("Mismatches", probes.get("failed", 0))
            if probes.get("status") == "passed":
                st.success("Selected side-effect-light functions produced matching source and target outputs for every executed probe case.")
            elif probes.get("status") == "failed":
                st.error("Behavioral probe mismatches were detected. The migration should not be treated as behaviorally verified.")
                failures = [r for r in probes.get("results", []) if r.get("status") == "failed"]
                if failures:
                    with st.expander(f"Behavioral mismatches ({len(failures)})"):
                        for item in failures:
                            st.write(f"- **{item.get('symbol')}** — inputs `{item.get('inputs')}`")
                            st.write(f"  - source: `{item.get('source_value')}`")
                            st.write(f"  - target: `{item.get('target_value')}`")
            elif probes.get("status") == "partial":
                st.warning("Some behavioral probes could not be executed. Treat the result as partial evidence.")
            else:
                st.info(probes.get("reason", "No safe behavioral probe candidates were available."))

            st.markdown("### Behavioral test evidence")
            if execution.get("status") == "passed":
                st.success(f"Target tests passed in {execution.get('duration_seconds', 0):.2f}s")
            elif execution.get("status") == "failed":
                st.error("Target tests failed. This evidence should block a release until repaired.")
                if execution.get("stderr"):
                    st.code(execution.get("stderr", ""), language="text")
            elif tests.get("count", 0):
                st.info("Target tests were discovered but could not be executed in the current environment.")
            else:
                st.info("No target test files were discovered. Contract evidence is still reported, but behavioral confidence is limited.")

            with st.expander("Verification methodology & limitations"):
                for limitation in data.get("limitations", []):
                    st.write(f"- {limitation}")

            st.markdown("### Release evidence & traceability")
            try:
                evidence = client.migration_evidence(semantic_name).get("data", {})
                security = evidence.get("security_review", {})
                provenance = evidence.get("provenance_manifest", {})
                trace = evidence.get("traceability_matrix", {})
                ec1, ec2, ec3, ec4 = st.columns(4)
                ec1.metric("Security", str(security.get("status", "not available")).replace("_", " ").title())
                ec2.metric("Critical findings", security.get("critical", 0))
                ec3.metric("Target files", provenance.get("target_file_count", 0))
                ec4.metric("Traced symbols", trace.get("matched_count", 0))
                if security.get("status") == "blocked":
                    st.error("Release evidence contains critical security findings.")
                elif security.get("status") == "review":
                    st.warning("Security review requires human inspection of high-risk findings.")
                else:
                    st.success("No deterministic critical/high security findings were detected by the built-in review.")
                unresolved = trace.get("unresolved", [])
                if unresolved:
                    with st.expander(f"Traceability exceptions ({len(unresolved)})"):
                        for item in unresolved[:100]:
                            st.write(f"- **{item.get('status')}**: {item.get('source')} → {item.get('target')}")
                with st.expander("Provenance"):
                    st.write(f"Model: `{provenance.get('model_id', 'unknown')}`")
                    st.write(f"Tool version: `{provenance.get('tool_version', 'unknown')}`")
                    st.write(f"Source files hashed: {provenance.get('source_file_count', 0)}")
                    st.write(f"Target files hashed: {provenance.get('target_file_count', 0)}")
            except ApiError:
                st.info("Release evidence is generated during post-migration analysis.")

        except ApiError as e:
            st.info("Semantic verification becomes available after post-migration analysis runs.")
    else:
        st.caption("Complete a migration, then enter its name here to inspect semantic verification evidence.")

# --------------------------------------------------------------------------
# Tab: Ask the Codebase
# --------------------------------------------------------------------------
if active_section == "Ask the Codebase":
    st.markdown('<div class="panel-kicker">CODE INTELLIGENCE</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">Ask the codebase why the migration looks the way it does.</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel-subtitle">Use the persisted migration knowledge base to inspect source or target behavior without exposing internal agent reasoning.</div>', unsafe_allow_html=True)

    chat_migration = st.text_input(
        "Migration name", value=st.session_state.active_migration_name or "", key="analysis_chat_migration"
    )
    is_target = st.checkbox("Ask about the target (converted) code", value=False)

    st.markdown('<div style="margin:.65rem 0 .35rem"><span class="release-label">Suggested questions</span></div>', unsafe_allow_html=True)
    prompt_cols = st.columns(3)
    prompts = [
        "What changed in the authentication flow?",
        "Which modules need the most review?",
        "How did the REST contract map to the target?",
    ]
    selected_prompt = None
    for idx, (col, prompt) in enumerate(zip(prompt_cols, prompts)):
        if col.button(prompt, key=f"prompt_{idx}", width="stretch"):
            selected_prompt = prompt
    question = st.text_area(
        "Your question",
        value=selected_prompt or "",
        placeholder="e.g. Why was the payment service split during migration?",
        height=110,
    )

    if st.button("Ask the codebase", type="primary", width="stretch"):
        if not chat_migration or not question.strip():
            st.warning("Enter a migration name and a question.")
        else:
            thinking_slot = st.empty()
            with thinking_slot:
                if not try_lottie(THINKING_LOTTIE_URL, height=120):
                    st.spinner("Searching migration evidence...")
            try:
                answer = client.chat_ask(chat_migration, question.strip(), is_target=is_target)
                thinking_slot.empty()
                render_codebase_answer(chat_migration, answer, is_target)
            except ApiError as e:
                thinking_slot.empty()
                st.error(e.detail)

# --------------------------------------------------------------------------
# Tab: About
# --------------------------------------------------------------------------
if active_section == "About":
    st.markdown(
        """
        ### How this works
        This UI talks directly to **agent_service**, a standalone FastAPI service that runs a
        multi-step AI agent pipeline (scan → knowledge base → plan → convert → package)
        over your uploaded project using Agno-orchestrated agent teams.

        - Uploaded projects are unpacked to a shared volume both containers can see.
        - agent_service resolves an identity from your bearer token — no separate login
          service required.
        - Progress is polled from `/v1/tasks/{task_id}`; the converted project is packaged
          into a downloadable zip once the run completes.
        """
    )
    st.caption("Built for standalone Docker deployment · agent_service + Streamlit")
