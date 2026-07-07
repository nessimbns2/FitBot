"""
RAG Engine — Gym Workout & Nutrition Knowledge Base
Handles PDF ingestion, embedding, vector storage, and retrieval-augmented generation.
"""

import os
import glob
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# ─── Configuration ───────────────────────────────────────────────────────────

VECTORSTORE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectorstore")
LLM_MODEL = "llama3.2:3b"
EMBEDDING_MODEL = "nomic-embed-text"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 4

# ─── System Prompt ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are FitBot 🏋️, an expert AI fitness and nutrition coach. 
You answer questions about gym workouts, exercise routines, nutrition plans, 
body type training, and healthy lifestyle choices.

Use the following pieces of retrieved context to answer the question. 
If the context contains relevant information, use it to provide a detailed, 
actionable answer. If the context doesn't contain enough information to fully 
answer the question, say so honestly and provide what you can based on the 
available context.

Guidelines:
- Be encouraging and motivational in your responses
- Provide specific, actionable advice when possible
- When discussing exercises, mention proper form cues for safety
- When discussing nutrition, mention portion sizes or macros when available
- Always cite which document your information comes from
- Format your responses with clear headings, bullet points, and structure

Context:
{context}

Chat History:
{chat_history}

Question: {question}

Helpful Answer:"""


# ─── PDF Ingestion ───────────────────────────────────────────────────────────

def get_pdf_files(pdf_dir: str) -> list[str]:
    """Find all PDF files in the given directory."""
    return glob.glob(os.path.join(pdf_dir, "*.pdf"))


def ingest_documents(pdf_dir: str, progress_callback=None) -> dict:
    """
    Load PDFs, chunk them, embed them, and store in a FAISS vector index.
    
    Args:
        pdf_dir: Path to directory containing PDF files
        progress_callback: Optional callable(current, total, message) for progress updates
        
    Returns:
        dict with keys: 'num_documents', 'num_chunks', 'documents_loaded'
    """
    pdf_files = get_pdf_files(pdf_dir)
    
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in {pdf_dir}")
    
    all_documents = []
    documents_loaded = []
    total_files = len(pdf_files)
    
    # Step 1: Load PDFs
    for i, pdf_path in enumerate(pdf_files):
        filename = os.path.basename(pdf_path)
        if progress_callback:
            progress_callback(i, total_files * 2, f"📄 Loading: {filename}")
        
        try:
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()
            
            # Enrich metadata
            for page in pages:
                page.metadata["source_filename"] = filename
                page.metadata["page_display"] = f"Page {page.metadata.get('page', 0) + 1}"
            
            all_documents.extend(pages)
            documents_loaded.append(filename)
        except Exception as e:
            print(f"[WARNING] Could not load {filename}: {e}")
            continue
    
    if not all_documents:
        raise ValueError("No documents could be loaded from the PDF files.")
    
    # Step 2: Split into chunks
    if progress_callback:
        progress_callback(total_files, total_files * 2, "✂️ Splitting documents into chunks...")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = text_splitter.split_documents(all_documents)
    
    # Step 3: Create embeddings and store in FAISS
    if progress_callback:
        progress_callback(total_files + 1, total_files * 2, "🧮 Generating embeddings (this may take a minute)...")
    
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = FAISS.from_documents(chunks, embeddings)
    
    # Step 4: Save to disk
    if progress_callback:
        progress_callback(total_files * 2 - 1, total_files * 2, "💾 Saving vector store...")
    
    os.makedirs(VECTORSTORE_DIR, exist_ok=True)
    vectorstore.save_local(VECTORSTORE_DIR)
    
    if progress_callback:
        progress_callback(total_files * 2, total_files * 2, "✅ Knowledge base ready!")
    
    return {
        "num_documents": len(all_documents),
        "num_chunks": len(chunks),
        "documents_loaded": documents_loaded
    }


# ─── RAG Chain ───────────────────────────────────────────────────────────────

def vectorstore_exists() -> bool:
    """Check if a FAISS vectorstore has been built."""
    return os.path.exists(os.path.join(VECTORSTORE_DIR, "index.faiss"))


def get_rag_chain():
    """
    Build and return the RAG chain using LCEL (fast, single LLM call).
    
    Returns:
        tuple of (chain, retriever)
    """
    if not vectorstore_exists():
        raise FileNotFoundError(
            "Vector store not found. Please build the knowledge base first."
        )
    
    # Load vectorstore
    embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL)
    vectorstore = FAISS.load_local(
        VECTORSTORE_DIR, embeddings, allow_dangerous_deserialization=True
    )
    
    # Create retriever
    retriever = vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": TOP_K}
    )
    
    # Create LLM
    llm = ChatOllama(
        model=LLM_MODEL,
        temperature=0.3,
    )
    
    # Create prompt
    prompt = PromptTemplate(
        template=SYSTEM_PROMPT,
        input_variables=["context", "chat_history", "question"]
    )
    
    return retriever, llm, prompt


def format_docs(docs):
    """Format retrieved documents into a single string."""
    return "\n\n---\n\n".join(doc.page_content for doc in docs)


def format_chat_history(history: list) -> str:
    """Format chat history list into a string for the prompt."""
    if not history:
        return "No previous conversation."
    
    formatted = []
    for msg in history[-10:]:  # Last 5 exchanges (10 messages)
        role = "Human" if msg["role"] == "user" else "Assistant"
        formatted.append(f"{role}: {msg['content'][:200]}")
    return "\n".join(formatted)


def query_rag(retriever, llm, prompt, question: str, chat_history: list = None) -> dict:
    """
    Query the RAG chain and return the answer with sources.
    Uses a single LLM call for faster responses.
    
    Args:
        retriever: The FAISS retriever
        llm: The ChatOllama LLM
        prompt: The PromptTemplate
        question: User's question
        chat_history: List of {"role": ..., "content": ...} dicts
        
    Returns:
        dict with 'answer' and 'sources' keys
    """
    # Retrieve relevant documents
    docs = retriever.invoke(question)
    
    # Format inputs
    context = format_docs(docs)
    history_str = format_chat_history(chat_history or [])
    
    # Build and invoke the chain (single LLM call)
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({
        "context": context,
        "chat_history": history_str,
        "question": question
    })
    
    # Extract and deduplicate sources
    sources = []
    seen = set()
    for doc in docs:
        source_key = (
            doc.metadata.get("source_filename", "Unknown"),
            doc.metadata.get("page_display", "Unknown page")
        )
        if source_key not in seen:
            seen.add(source_key)
            sources.append({
                "filename": source_key[0],
                "page": source_key[1],
                "snippet": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            })
    
    return {
        "answer": answer,
        "sources": sources
    }


def query_rag_stream(retriever, llm, prompt, question: str, chat_history: list = None):
    """
    Stream the RAG chain response token-by-token.
    Yields dicts: {"type": "token", "content": "..."} and {"type": "sources", "sources": [...]}
    """
    # Retrieve relevant documents
    docs = retriever.invoke(question)

    # Format inputs
    context = format_docs(docs)
    history_str = format_chat_history(chat_history or [])

    # Extract sources first and yield them
    sources = []
    seen = set()
    for doc in docs:
        source_key = (
            doc.metadata.get("source_filename", "Unknown"),
            doc.metadata.get("page_display", "Unknown page")
        )
        if source_key not in seen:
            seen.add(source_key)
            sources.append({
                "filename": source_key[0],
                "page": source_key[1],
                "snippet": doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            })

    yield {"type": "sources", "sources": sources}

    # Stream the LLM response token by token
    chain = prompt | llm
    for chunk in chain.stream({
        "context": context,
        "chat_history": history_str,
        "question": question
    }):
        token = chunk.content if hasattr(chunk, 'content') else str(chunk)
        if token:
            yield {"type": "token", "content": token}

