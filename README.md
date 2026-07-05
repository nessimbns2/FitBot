# FitBot 🏋️ — Gym Workout & Nutrition RAG Backend API

A fully local, privacy-first REST API backend that manages chat sessions and answers gym workout and nutrition questions using PDF documents as a RAG (Retrieval-Augmented Generation) knowledge base.

Designed to be integrated into any frontend web application (React, Next.js, Vue, HTML/JS, etc.).

---

## ⚡ Quick Start

### 1. Install & Configure Ollama

1. Download and install Ollama from [ollama.com](https://ollama.com).
2. Pull the AI models in your terminal:
   ```bash
   ollama pull llama3.1:8b
   ollama pull nomic-embed-text
   ```

> **💡 GPU/CUDA Crashes?**
> If Ollama crashes on Windows due to driver issues, disable GPU by setting this user environment variable in PowerShell:
> ```powershell
> [System.Environment]::SetEnvironmentVariable('CUDA_VISIBLE_DEVICES', '-1', 'User')
> ```
> Then restart Ollama.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the API Server

```bash
python main.py
```
The server will start running at **`http://localhost:8000`** with auto-reload enabled.

---

## 📁 API Endpoints Reference

### 🌐 CORS Setup
CORS is configured to accept requests from all origins (`*`), so you can run your frontend on any port (e.g. `localhost:3000` or `localhost:5173`) and call this API directly.

### 1. System Status
* **Endpoint:** `GET /status`
* **Response:**
  ```json
  {
    "vectorstore_exists": true,
    "available_pdfs": [
      "360Nutritionprogram1.pdf",
      "BodyType+Training+and+Nutrition.pdf",
      "EndomorphEvolution.pdf"
    ],
    "loaded_sessions": []
  }
  ```

### 2. Build / Ingest PDFs
Extracts, chunks, embeds, and saves the vector database index on disk.
* **Endpoint:** `POST /ingest`
* **Request Body:**
  ```json
  {
    "pdf_dir": null
  }
  ```
* **Response:**
  ```json
  {
    "status": "success",
    "num_documents": 218,
    "num_chunks": 845,
    "documents_loaded": [
      "360Nutritionprogram1.pdf",
      "BodyType+Training+and+Nutrition.pdf"
    ]
  }
  ```

### 3. Chat Session Query
Sends a message to the bot under a specific session ID. The backend maintains the session history automatically in-memory.
* **Endpoint:** `POST /chat`
* **Request Body:**
  ```json
  {
    "session_id": "session_abc123",
    "message": "What is functional training?"
  }
  ```
* **Response:**
  ```json
  {
    "answer": "Functional training is a series of exercises...",
    "sources": [
      {
        "filename": "Functional-Training-Guide-IAFS.pdf",
        "page": "Page 22",
        "snippet": "Functional training consists of a series..."
      }
    ]
  }
  ```

### 4. Sessions List
* **Endpoint:** `GET /sessions`
* **Response:**
  ```json
  ["session_abc123"]
  ```

### 5. Session History
* **Endpoint:** `GET /sessions/{session_id}`
* **Response:**
  ```json
  [
    {"role": "user", "content": "What is functional training?"},
    {"role": "assistant", "content": "Functional training is a..."}
  ]
  ```

### 6. Reset Session
* **Endpoint:** `DELETE /sessions/{session_id}`
* **Response:**
  ```json
  {
    "status": "cleared",
    "session_id": "session_abc123"
  }
  ```
