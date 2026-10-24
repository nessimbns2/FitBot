# ─── FitBot Backend Dockerfile ─────────────────────────────────────────────
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Configure non-root user (UID 1000 required for Hugging Face Spaces / cloud platforms)
RUN useradd -m -u 1000 user
ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user/app
RUN chown -R user:user /home/user

# Switch to the non-root user
USER user

# Install Python requirements
COPY --chown=user:user backend/requirements_v2.txt ./backend/
RUN pip install --no-cache-dir --user -r backend/requirements_v2.txt

# Copy backend files and documents
COPY --chown=user:user backend/ ./backend/
COPY --chown=user:user start.sh ./

# Make the start script executable
RUN chmod +x start.sh

# Expose default port (7860 for Hugging Face Spaces, 8000 default)
EXPOSE 8000 7860
ENV PORT=8000

# Run entrypoint script
CMD ["./start.sh"]
