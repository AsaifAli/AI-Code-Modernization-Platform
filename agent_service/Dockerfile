# syntax=docker/dockerfile:1.7
FROM node:20-bookworm-slim AS node_runtime
FROM python:3.11-slim

COPY --from=node_runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node_runtime /usr/local/lib/node_modules /usr/local/lib/node_modules

RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version && npx --version

ARG STACK_ANALYZER_VERSION=1.27.6
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev curl universal-ctags \
    && ctags --version | grep -qi "Universal Ctags" \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN PIP_DEFAULT_TIMEOUT=600 PIP_RETRIES=10 PIP_REQUIRE_HASHES=0 \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

RUN npm install --global --omit=dev @specfy/stack-analyser@${STACK_ANALYZER_VERSION:-1.27.6} \
    && stack-analyser --help >/dev/null

COPY . .
RUN python -c "from app.infrastructure.utils.Agent_helpers.planning_helper import AgentConstants; assert AgentConstants.PLANNING_AGENT"

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/Temp \
    && chown -R appuser:appuser /app

USER appuser

ENV SERVICE_HOST=0.0.0.0 \
    AGENT_SERVICE_PORT=8015 \
    PYTHONUNBUFFERED=1

EXPOSE 8015
VOLUME ["/app/Temp"]

CMD ["sh", "-c", "AGENT_SERVICE_PORT=${PORT:-8015} SERVICE_HOST=0.0.0.0 python main.py"]
