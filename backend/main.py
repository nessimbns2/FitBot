"""
FitBot 🏋️ — Gym Workout & Nutrition RAG Backend
FastAPI backend service for local AI retrieval-augmented generation and session-based chat.
"""

import os
import json
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import uvicorn

from rag_engine import (
    ingest_documents,
    get_rag_chain,
    query_rag,
    query_rag_stream,
    vectorstore_exists,
    get_pdf_files
)

# ─── API Setup ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="FitBot RAG API",
    description="Local RAG chatbot API for gym workouts and nutrition plans.",
    version="1.0.0"
)

# Enable CORS for frontend integration (e.g. React, Vue, Next.js, HTML/JS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-Memory Session Storage ──────────────────────────────────────────────

# Dict structure: { session_id: [ {"role": "user", "content": "..."}, {"role": "assistant", "content": "..."} ] }
sessions_db: Dict[str, List[Dict[str, str]]] = {}

# Cached RAG components (retriever, llm, prompt) to avoid loading them repeatedly
rag_components = None

def load_rag_components():
    global rag_components
    if rag_components is None and vectorstore_exists():
        rag_components = get_rag_chain()
    return rag_components

# ─── Models ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique ID for the chat session")
    message: str = Field(..., description="User message to the chatbot")

class SourceCitation(BaseModel):
    filename: str
    page: str
    snippet: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceCitation]

class IngestRequest(BaseModel):
    pdf_dir: Optional[str] = Field(None, description="Directory path containing PDFs. Defaults to app directory.")

class IngestResponse(BaseModel):
    status: str
    num_documents: int
    num_chunks: int
    documents_loaded: List[str]

class StatusResponse(BaseModel):
    vectorstore_exists: bool
    available_pdfs: List[str]
    loaded_sessions: List[str]

# ─── Endpoints ──────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    # Attempt to pre-load RAG components if vector store is already built
    try:
        load_rag_components()
        print("[SUCCESS] RAG components preloaded successfully.")
    except Exception as e:
        print(f"[WARNING] RAG components could not be preloaded on startup: {e}")

@app.get("/status", response_model=StatusResponse)
def get_status():
    """Get the current system status, available PDFs, and active sessions."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pdf_dir = os.path.join(project_root, "documents")
    available_pdfs = [os.path.basename(f) for f in get_pdf_files(pdf_dir)]
    return {
        "vectorstore_exists": vectorstore_exists(),
        "available_pdfs": available_pdfs,
        "loaded_sessions": list(sessions_db.keys())
    }

@app.post("/ingest", response_model=IngestResponse)
def trigger_ingestion(request: IngestRequest):
    """Build or rebuild the FAISS vector database from PDF documents."""
    global rag_components
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_pdf_dir = os.path.join(project_root, "documents")
    pdf_dir = request.pdf_dir or default_pdf_dir
    
    try:
        stats = ingest_documents(pdf_dir)
        # Invalidate cached components so they get reloaded on next query
        rag_components = None
        return {
            "status": "success",
            "num_documents": stats["num_documents"],
            "num_chunks": stats["num_chunks"],
            "documents_loaded": stats["documents_loaded"]
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """Send a message to a session and get a response from the RAG pipeline."""
    # Ensure vector store exists
    if not vectorstore_exists():
        raise HTTPException(
            status_code=400, 
            detail="Knowledge base not built. Please run /ingest first."
        )
    
    # Load components
    components = load_rag_components()
    if not components:
        raise HTTPException(
            status_code=500,
            detail="Failed to load RAG components. Make sure Ollama is running."
        )
    
    retriever, llm, prompt_template = components
    session_id = request.session_id
    user_message = request.message
    
    # Initialize session if not exists
    if session_id not in sessions_db:
        sessions_db[session_id] = []
        
    # Get current session history
    history = sessions_db[session_id]
    
    try:
        # Run query
        result = query_rag(
            retriever=retriever,
            llm=llm,
            prompt=prompt_template,
            question=user_message,
            chat_history=history
        )
        
        # Append exchanges to in-memory history
        history.append({"role": "user", "content": user_message})
        history.append({"role": "assistant", "content": result["answer"]})
        
        return {
            "answer": result["answer"],
            "sources": result["sources"]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error querying model: {str(e)}. Tip: Verify Ollama is running and models are pulled."
        )

@app.post("/chat/stream")
def chat_stream_endpoint(request: ChatRequest):
    """Stream a response from the RAG pipeline using Server-Sent Events."""
    if not vectorstore_exists():
        raise HTTPException(
            status_code=400,
            detail="Knowledge base not built. Please run /ingest first."
        )

    components = load_rag_components()
    if not components:
        raise HTTPException(
            status_code=500,
            detail="Failed to load RAG components. Make sure Ollama is running."
        )

    retriever, llm, prompt_template = components
    session_id = request.session_id
    user_message = request.message

    if session_id not in sessions_db:
        sessions_db[session_id] = []

    history = sessions_db[session_id]

    def event_generator():
        try:
            full_answer = ""
            sources = []
            for event in query_rag_stream(
                retriever=retriever,
                llm=llm,
                prompt=prompt_template,
                question=user_message,
                chat_history=history
            ):
                if event["type"] == "token":
                    full_answer += event["content"]
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "sources":
                    sources = event["sources"]
                    yield f"data: {json.dumps(event)}\n\n"
                elif event["type"] == "heartbeat":
                    # SSE comment to keep connection alive
                    yield ": heartbeat\n\n"
                elif event["type"] == "error":
                    yield f"data: {json.dumps(event)}\n\n"

            # Save to session history
            history.append({"role": "user", "content": user_message})
            history.append({"role": "assistant", "content": full_answer})

            # Send done event
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )

@app.get("/sessions", response_model=List[str])
def list_sessions():
    """List all active session IDs in memory."""
    return list(sessions_db.keys())

@app.get("/sessions/{session_id}", response_model=List[Dict[str, str]])
def get_session_history(session_id: str):
    """Retrieve chat history list for a specific session ID."""
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session ID not found")
    return sessions_db[session_id]

@app.delete("/sessions/{session_id}")
def clear_session(session_id: str):
    """Clear memory history for a session."""
    if session_id in sessions_db:
        del sessions_db[session_id]
        return {"status": "cleared", "session_id": session_id}
    raise HTTPException(status_code=404, detail="Session ID not found")

# ─── Local Server Execution ──────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
