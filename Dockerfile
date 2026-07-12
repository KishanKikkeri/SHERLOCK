# SHERLOCK — production image
#
# Builds the frontend (Vite) and installs the backend, then serves both
# from a single FastAPI process (backend/app/server.py mounts the built
# frontend at "/" and the API alongside it).
#
# Build:
#   docker build -t sherlock .
# Run (SQLite + NetworkX, zero external services):
#   docker run -p 8000:8000 sherlock
# Run against Postgres/Neo4j (see docker/docker-compose.yml):
#   docker compose -f docker/docker-compose.yml up

FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

# System deps for psycopg2 (only needed if DATABASE_URL points at Postgres)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY demo_investigation.py demo_graph_queries.py ./
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "backend.app.server"]
