# ─────────────────────────────────────────────────────────────────────────────
# FinBot API — Hugging Face Spaces Docker Image
# HF Spaces requires the app to listen on port 7860 and run as a non-root user.
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── System deps ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user (HF Spaces requirement) ────────────────────────────────────
RUN useradd -m -u 1000 appuser

WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Copy application code ─────────────────────────────────────────────────────
COPY . .

# ── Fix ownership ─────────────────────────────────────────────────────────────
RUN chown -R appuser:appuser /app

USER appuser

# ── Entrypoint ────────────────────────────────────────────────────────────────
# startup.sh: runs Alembic migrations first, then starts uvicorn
RUN chmod +x /app/startup.sh

EXPOSE 7860

CMD ["/bin/bash", "/app/startup.sh"]
