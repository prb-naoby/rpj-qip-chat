# =============================================================================
# QIP Chat - Single Image (Multi-Mode)
# =============================================================================
# One image that can run as either frontend or backend
# Usage:
#   - Frontend: docker run -e MODE=frontend -p 3000:3000 ghcr.io/prb-naoby/rpj-qip-chat
#   - Backend:  docker run -e MODE=backend -p 1234:1234 ghcr.io/prb-naoby/rpj-qip-chat
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build Frontend
# -----------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: Combined Runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    bash \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY api/ ./api/
COPY app/ ./app/

# Copy built frontend from builder stage
COPY --from=frontend-builder /frontend/.next/standalone ./frontend/
COPY --from=frontend-builder /frontend/.next/static ./frontend/.next/static
COPY --from=frontend-builder /frontend/public ./frontend/public

# Create data directory
RUN mkdir -p /app/data

# Copy and setup entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Default to backend mode
ENV MODE=backend

# Expose both ports (only one will be used depending on mode)
EXPOSE 1234 3000

# Health check - checks based on MODE environment variable
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD if [ "$MODE" = "frontend" ]; then curl -f http://localhost:3000/; else curl -f http://localhost:1234/health; fi

ENTRYPOINT ["/app/entrypoint.sh"]
