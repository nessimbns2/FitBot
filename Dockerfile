# ─── Backend-Only Image (Python + Ollama) ─────────────────────────────────────
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    procps \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Configure non-root user (UID 1000 required for Hugging Face Spaces)
RUN useradd -m -u 1000 user
ENV HOME=/home/user
ENV PATH=/home/user/.local/bin:$PATH

WORKDIR /home/user/app
RUN chown -R user:user /home/user

# Switch to the non-root user
USER user

# Install Python requirements
COPY --chown=user:user backend/requirements.txt ./backend/
RUN pip install --no-cache-dir --user -r backend/requirements.txt

# Copy backend files and documents
COPY --chown=user:user backend/ ./backend/
COPY --chown=user:user documents/ ./documents/
COPY --chown=user:user start.sh ./

# Set CPU mode for Ollama on Hugging Face CPU Spaces
ENV CUDA_VISIBLE_DEVICES=-1
ENV OLLAMA_NUM_PARALLEL=1

# Make the start script executable
RUN chmod +x start.sh

# Hugging Face Spaces forwards traffic to port 7860
EXPOSE 7860
ENV PORT=7860

# Run entrypoint script
CMD ["./start.sh"]
