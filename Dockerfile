# Use python:3.12-slim-trixie as base image (identical to Dockerfile)
FROM python:3.12-slim-trixie

# Environment variables (EXACT MATCH with Dockerfile for layer sharing)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:/app/.venv/bin:$PATH \
    GRADIO_SERVER_NAME="0.0.0.0" \
    GRADIO_SERVER_PORT=7860

# Setup user and install system dependencies in one layer (identical to Dockerfile)
RUN useradd -m -u 1000 user && \
    apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official binary (identical to Dockerfile)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory and adjust ownership (identical to Dockerfile)
WORKDIR /app
RUN chown user:user /app

# Switch to non-root user (identical to Dockerfile)
USER user

# 1. Copy ONLY dependency files for optimal layer caching (identical to Dockerfile)
COPY --chown=user pyproject.toml uv.lock ./

# 2. Install dependencies (identical to Dockerfile)
RUN uv sync --frozen --no-cache

# 3. Copy the application code LAST (identical to Dockerfile)
COPY --chown=user . .

# Expose port 7860 (same as Gradio)
EXPOSE 7860

# Run the Streamlit application on port 7860
CMD ["uv", "run", "streamlit", "run", "streamlit_app.py", "--server.port=7860", "--server.address=0.0.0.0"]
