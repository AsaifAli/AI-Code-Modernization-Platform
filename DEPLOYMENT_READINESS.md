# Deployment Readiness

Status: Phase 1 hardened; resource-intensive flagship deployment.

Cloud shape: separate Streamlit UI and FastAPI agent service. PostgreSQL and LLM access must be externalized. vLLM is a local/GPU development profile and is not part of the Render deployment. The backend is unlikely to be a sensible Render Free workload because of its dependency and runtime footprint.
