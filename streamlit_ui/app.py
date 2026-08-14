"""Streamlit UI for the standalone agent_service — upload a project, run an
AI-assisted migration, and watch it happen."""
from __future__ import annotations

import os
import json
import time
import uuid
from pathlib import Path

import requests
import streamlit as st

from api_client import AgentServiceClient, ApiError, DEFAULT_BASE_URL

# --------------------------------------------------------------------------
# Page config & constants
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Code Migration Studio",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');

    html, body, [class*="css"]  { font-family: 'Inter', sans-serif; }

    .hero {
        position: relative;
        border-radius: 18px;
        overflow: hidden;
        padding: 2.6rem 2.2rem;
        margin-bottom: 1.6rem;
        background: linear-gradient(120deg, #4f46e5, #7c3aed, #06b6d4);
        color: white;
        box-shadow: 0 10px 30px rgba(79, 70, 229, 0.25);
    }
    .hero h1 { font-weight: 800; font-size: 2.4rem; margin-bottom: 0.3rem; }
    .hero p { font-size: 1.05rem; opacity: 0.92; max-width: 640px; }

    /* Status dot: solid color, no idle motion. Pulse is reserved for the
       brief moment a check is actually in flight (see .status-dot.checking). */
    .status-dot {
        display: inline-block;
        width: 10px; height: 10px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-dot.online { background: #22c55e; }
    .status-dot.offline { background: #ef4444; }
    .status-dot.checking { background: #94a3b8; animation: pulse 1.2s infinite; }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(148, 163, 184, 0.55); }
        70% { box-shadow: 0 0 0 8px rgba(148, 163, 184, 0); }
        100% { box-shadow: 0 0 0 0 rgba(148, 163, 184, 0); }
    }

    .fade-in { animation: fadeIn 0.6s ease-in; }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .glass-card {
        background: rgba(255, 255, 255, 0.55);
        border: 1px solid rgba(120, 120, 160, 0.15);
        border-radius: 14px;
        padding: 1.1rem 1.3rem;
        margin-bottom: 0.9rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .glass-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 22px rgba(30, 30, 60, 0.12);
    }

    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        transition: transform 0.12s ease;
    }
    .stButton>button:hover { transform: translateY(-1px); }

    .badge {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.02em;
    }
    .badge.running { background: #fef9c3; color: #854d0e; }
    .badge.completed { background: #dcfce7; color: #166534; }
    .badge.failed { background: #fee2e2; color: #991b1b; }

    .completion-card {
        border: 1px solid #bbf7d0;
        background: linear-gradient(135deg, #f0fdf4, #f8fafc);
        border-radius: 14px;
        padding: 1rem 1.1rem;
        margin: 0.8rem 0 1rem 0;
    }
    .completion-title {
        font-size: 1.05rem; font-weight: 800; color: #166534;
    }
    .completion-subtitle {
        margin-top: 0.2rem; color: #475569; font-size: 0.9rem;
    }

    /* Skeleton loading shimmer, shown while a request is in flight */
    .skeleton {
        border-radius: 10px;
        background: linear-gradient(90deg, #eceef3 25%, #f7f8fb 37%, #eceef3 63%);
        background-size: 400% 100%;
        animation: shimmer 1.4s ease infinite;
    }
    @keyframes shimmer {
        0% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    /* Unified tachometer-style migration progress */
    .gauge-wrap { display:flex; flex-direction:column; align-items:center; margin:1rem 0 0.75rem; }
    .gauge { position:relative; width:250px; height:135px; overflow:hidden; }
    .gauge-arc { position:absolute; left:12px; top:8px; width:226px; height:226px; border-radius:50%; background:conic-gradient(from 270deg, #22c55e 0deg, #06b6d4 92deg, #7c3aed 180deg, #e5e7eb 180deg 360deg); }
    .gauge-arc::after { content:""; position:absolute; inset:24px; border-radius:50%; background:#ffffff; }
    .gauge-needle { position:absolute; left:50%; bottom:14px; width:4px; height:92px; transform-origin:50% 100%; background:#111827; border-radius:999px; z-index:2; }
    .gauge-pin { position:absolute; left:50%; bottom:8px; width:14px; height:14px; margin-left:-7px; border-radius:50%; background:#111827; z-index:3; }
    .gauge-value { position:absolute; left:0; right:0; bottom:18px; text-align:center; font-size:1.6rem; font-weight:800; color:#111827; z-index:3; }
    .gauge-label { font-size:0.82rem; color:#6b7280; margin-top:-0.1rem; }
    .gauge-message { text-align:center; font-weight:600; margin-top:0.35rem; color:#374151; }

    /* Spinning icon — reserved for genuine in-progress states, not idle decoration. */
    .spin-icon { display: inline-block; animation: spin 1.6s linear infinite; }
    @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
if "base_url" not in st.session_state:
    st.session_state.base_url = DEFAULT_BASE_URL
if "token" not in st.session_state:
    st.session_state.token = "streamlit-user"
if "active_task_id" not in st.session_state:
    st.session_state.active_task_id = None
if "active_migration_name" not in st.session_state:
    st.session_state.active_migration_name = None
if "active_task_started_at" not in st.session_state:
    st.session_state.active_task_started_at = None
if "active_section_widget" not in st.session_state:
    st.session_state.active_section_widget = "New Migration"


def get_client() -> AgentServiceClient:
    return AgentServiceClient(base_url=st.session_state.base_url, token=st.session_state.token)


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


# The backend now streams Agno Workflow step events into the task status API.
# This UI renders those persisted events; it is no longer a time-based approximation.
PIPELINE_STAGES = [
    ("🔍", "Scan source"), ("🛡️", "Verify scan"), ("🧠", "Build knowledge base"),
    ("🗺️", "Plan migration"), ("🛡️", "Verify plan"), ("🔄", "Convert code"),
    ("🧪", "Post-migration engineering"),
]

def render_live_plan(progress: dict):
    """Render one unified tachometer-style progress indicator."""
    plan = progress.get("plan") or []
    if not plan:
        return
    completed = sum(1 for x in plan if x.get("status") == "complete")
    running_index = next((i for i, x in enumerate(plan) if x.get("status") in {"running", "in_progress"}), None)
    pct = 100 if completed == len(plan) else int(((running_index if running_index is not None else completed) / len(plan)) * 100)
    pct = max(0, min(100, pct))
    angle = -90 + (pct * 1.8)
    message = str(progress.get("message", "Executing migration workflow"))
    current = next((x.get("name") for x in plan if x.get("status") in {"running", "in_progress"}), None)
    label = current or ("Migration complete" if pct >= 100 else "Preparing migration")
    html = (
        '<div class="gauge-wrap">'
        '<div class="gauge">'
        '<div class="gauge-arc"></div>'
        f'<div class="gauge-needle" style="transform:translateX(-50%) rotate({angle}deg);"></div>'
        '<div class="gauge-pin"></div>'
        f'<div class="gauge-value">{pct}%</div>'
        '</div>'
        f'<div class="gauge-label">{completed}/{len(plan)} stages complete</div>'
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
    st.markdown("### Connection")
    st.session_state.base_url = st.text_input("agent_service URL", st.session_state.base_url)
    st.session_state.token = st.text_input(
        "Your identity token",
        st.session_state.token,
        help=(
            "agent_service runs standalone: any bearer token you type here becomes a stable "
            "local identity, scoping which migrations you see. Use the same value across "
            "sessions to see your past migrations."
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
    st.markdown(
        f'<span class="status-dot {dot_class}"></span>**{label}**',
        unsafe_allow_html=True,
    )
    if not online:
        st.caption("Check the URL and that agent_service is running.")

# --------------------------------------------------------------------------
# Hero
# --------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="hero fade-in">
        <h1>AI Code Migration Studio</h1>
        <p>Upload a legacy codebase, describe where you want it to go, and let the
        agent_service AI team scan, plan, and convert it — live, end to end.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Use a stateful navigation control instead of st.tabs. Native st.tabs reset to
# the first tab after every st.rerun(), which made the live migration view jump
# away during Verify Plan / conversion and made completed runs hard to return to.
SECTIONS = [
    "New Migration",
    "My Migrations",
    "Architecture & Analysis",
    "Semantic Verification",
    "Ask the Codebase",
    "About",
]
# Keep widget-owned state separate from application state. Streamlit forbids
# mutating a widget's keyed session state after the widget is instantiated.
# The widget itself is therefore the single source of truth for navigation.
active_section = st.segmented_control(
    "Migration sections",
    SECTIONS,
    key="active_section_widget",
    selection_mode="single",
    label_visibility="collapsed",
)

# --------------------------------------------------------------------------
# Tab: New Migration
# --------------------------------------------------------------------------
if active_section == "New Migration":
    left, right = st.columns([1.3, 1])

    with left:
        st.markdown("#### 1. Upload your source project (.zip)")
        source_zip = st.file_uploader("Source project archive", type=["zip"], key="source_zip")
        target_zip = st.file_uploader(
            "Optional: existing target project archive", type=["zip"], key="target_zip"
        )

        st.markdown("#### 2. Describe the migration")
        migration_name = st.text_input(
            "Migration name", placeholder="e.g. billing-service-to-fastapi"
        )
        description = st.text_area(
            "Describe what you want",
            placeholder="Migrate this Java Spring service to a Python FastAPI microservice, "
                        "keeping the existing REST contract...",
            height=110,
        )
        col_a, col_b = st.columns(2)
        with col_a:
            target_language = st.selectbox("Target language (optional, auto-detected)", TARGET_LANGUAGES)
        with col_b:
            github_token = st.text_input("GitHub token (optional)", type="password")

        launch = st.button("Launch migration", type="primary", width='stretch')

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
                    st.toast(f"Migration '{migration_name}' queued")
                    st.success(f"Migration queued! Task ID `{result['task_id']}`")

                    detected = {
                        k.replace("detected_", "").replace("_", " ").title(): v
                        for k, v in result.items()
                        if k.startswith("detected_") and v not in (None, False, "")
                    }
                    if detected:
                        st.markdown("**Detected stack:**")
                        st.json(detected, expanded=False)
                except ApiError as e:
                    st.error(f"Failed to launch migration: {e.detail}")

    with right:
        st.markdown("#### Live status")
        if not st.session_state.active_task_id:
            st.caption("Launch a migration to see live progress here.")
        else:
            placeholder = st.container()
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
                    f'<span class="badge {badge_class}">{state.upper()}</span>',
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
                    if progress:
                        render_live_plan(progress)
                    else:
                        st.progress(0.02, text="Preparing workflow telemetry…")
                    try_lottie(LOADING_LOTTIE_URL, height=100)
                elif badge_class == "completed":
                    # Terminal state: do not auto-rerun and do not use celebratory
                    # balloons. Keep the result visible as a professional release
                    # status card and leave the task available for inspection.
                    if not st.session_state.get("completion_toast_shown"):
                        st.toast("Migration completed", icon="✓")
                        st.session_state.completion_toast_shown = True
                    st.markdown(
                        """
                        <div class="completion-card">
                            <div class="completion-title">Migration complete</div>
                            <div class="completion-subtitle">The workflow reached a terminal state. Review the evidence below before downloading the release.</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    raw_completed = status.get("result")
                    completed_payload = {}
                    if isinstance(raw_completed, str):
                        try:
                            parsed_completed = json.loads(raw_completed)
                            if isinstance(parsed_completed, dict) and parsed_completed.get("kind") == "completed":
                                completed_payload = parsed_completed
                        except Exception:
                            pass
                    if completed_payload.get("plan"):
                        render_live_plan({"plan": completed_payload["plan"], "percent": 100, "message": "All migration stages completed"})
                    if st.session_state.active_migration_name and completed_payload.get("release_ready", True):
                        try:
                            data = client.download_migration(st.session_state.active_migration_name)
                            st.download_button(
                                "Download converted project",
                                data=data,
                                file_name=f"{st.session_state.active_migration_name}.zip",
                                mime="application/zip",
                                width='stretch',
                            )
                        except ApiError:
                            st.caption("Download will be available shortly.")
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
                    release_ready = bool(failed_payload.get("release_ready"))
                    output_message = failed_payload.get("message") or status.get("error") or "Migration did not pass the release gate."
                    if failed_payload.get("kind") == "blocked" or "release gate" in str(output_message).lower():
                        if st.session_state.active_migration_name:
                            try:
                                data = client.download_migration(st.session_state.active_migration_name)
                                st.download_button(
                                    "Download converted project",
                                    data=data,
                                    file_name=f"{st.session_state.active_migration_name}.zip",
                                    mime="application/zip",
                                    width='stretch',
                                    key="blocked_demo_download",
                                )
                            except ApiError:
                                st.caption("Download will be available shortly.")
                    else:
                        st.error(f"Migration failed: {output_message}")

                if status.get("result"):
                    with st.expander("Result details"):
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
# Tab: Chat
# --------------------------------------------------------------------------
if active_section == "Ask the Codebase":
    st.markdown("#### Ask questions about a migrated codebase")
    chat_migration = st.text_input(
        "Migration name", value=st.session_state.active_migration_name or ""
    )
    question = st.text_area("Your question", placeholder="What does the payment module do?")
    is_target = st.checkbox("Ask about the target (converted) code instead of source")

    if st.button("Ask", type="primary"):
        if not chat_migration or not question:
            st.warning("Enter a migration name and a question.")
        else:
            thinking_slot = st.empty()
            with thinking_slot:
                if not try_lottie(THINKING_LOTTIE_URL, height=120):
                    st.spinner("Thinking...")
            try:
                answer = client.chat_ask(chat_migration, question, is_target=is_target)
                thinking_slot.empty()
                typewriter(answer["answer"])
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
