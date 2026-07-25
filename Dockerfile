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
# Copy Demo Assets
# -----------------------------------------------------------------------------

COPY sherlock.db ./

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

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1


# -----------------------------------------------------------------------------
# Start SHERLOCK
# -----------------------------------------------------------------------------

CMD ["python", "-m", "backend.app.server"]