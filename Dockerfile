# =============================================================================
# SHERLOCK - Production Docker Image
#
# Multi-stage build:
#   Stage 1 -> Build React/Vite frontend
#   Stage 2 -> Install FastAPI backend
#
# Result:
#   One container serving both frontend and backend.
#
# =============================================================================

##############################
# Stage 1 - Build Frontend
##############################

FROM node:20-slim AS frontend-build

WORKDIR /app/frontend

# Same-origin by default: the backend serves this build and the API from
# one process/port, so a relative base URL always resolves correctly
# without per-environment configuration. This is what fixes the app
# always landing on /login — without it, the built JS calls
# http://localhost:8000 from the visitor's browser, which fails, and the
# app treats any failed auth check as "not logged in".
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL

COPY frontend/package.json frontend/package-lock.json ./

RUN npm ci

COPY frontend/ ./

RUN npm run build


##############################
# Stage 2 - Backend Runtime
##############################

FROM python:3.11-slim

WORKDIR /app

# -----------------------------------------------------------------------------
# Install system packages
# -----------------------------------------------------------------------------

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    espeak-ng \
    curl \
    && rm -rf /var/lib/apt/lists/*


# -----------------------------------------------------------------------------
# Python dependencies
# -----------------------------------------------------------------------------

COPY backend/requirements.txt ./backend/requirements.txt

RUN pip install --no-cache-dir -r backend/requirements.txt


# -----------------------------------------------------------------------------
# Copy Backend
# -----------------------------------------------------------------------------

COPY backend/ ./backend/


# -----------------------------------------------------------------------------
# Copy Frontend Build
# -----------------------------------------------------------------------------

COPY --from=frontend-build /app/frontend/dist ./frontend/dist


# -----------------------------------------------------------------------------
# Generate/Populate Database
# -----------------------------------------------------------------------------

COPY reset_database.sql ./
RUN python -c "import sqlite3; conn = sqlite3.connect('sherlock.db'); conn.executescript(open('reset_database.sql', 'r', encoding='utf-8').read()); conn.close()" && rm reset_database.sql

COPY demo_investigation.py ./
COPY demo_graph_queries.py ./


# -----------------------------------------------------------------------------
# Runtime Configuration
# -----------------------------------------------------------------------------

ENV PYTHONUNBUFFERED=1

EXPOSE 8000


# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------
# Uses the same env var the app itself reads for its listen port, so this
# still works whatever port Catalyst AppSail actually assigns at runtime.

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:${X_ZOHO_CATALYST_LISTEN_PORT:-8000}/health || exit 1


# -----------------------------------------------------------------------------
# Start SHERLOCK
# -----------------------------------------------------------------------------

CMD ["python", "-m", "backend.app.server"]