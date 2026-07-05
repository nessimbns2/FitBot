#!/bin/bash

# Exit immediately if any command fails
set -e

# Start Ollama service in the background
echo "🚀 Starting Ollama service..."
ollama serve &

# Wait for Ollama service to start listening on port 11434
echo "⏳ Waiting for Ollama service to initialize..."
until curl -s http://127.0.0.1:11434/api/tags > /dev/null; do
    sleep 1
done

echo "✅ Ollama service is up and running!"

# Pull the models at runtime
echo "⏳ Checking and pulling AI models (this will only download on first cold-start)..."
ollama pull nomic-embed-text
ollama pull llama3.1:8b

# Start the FastAPI application
echo "🚀 Starting FastAPI application..."
cd backend
python main.py
