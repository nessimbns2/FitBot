import { useState, useEffect, useRef } from 'react';
import { 
  Plus, 
  Trash2, 
  Send, 
  Database, 
  RefreshCw, 
  FileText, 
  ChevronDown, 
  ChevronUp, 
  Dumbbell, 
  MessageSquare, 
  Sparkles, 
  CheckCircle2, 
  AlertCircle, 
  Loader2,
  BookOpen
} from 'lucide-react';

const API_URL = window.location.origin === 'http://localhost:5173' 
  ? 'http://localhost:8000' 
  : window.location.origin;

function App() {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [status, setStatus] = useState({
    vectorstore_exists: false,
    available_pdfs: [],
    loaded_sessions: []
  });
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestionStatusText, setIngestionStatusText] = useState('');
  const [expandedSources, setExpandedSources] = useState({});

  const messagesEndRef = useRef(null);

  // Load initial configurations
  useEffect(() => {
    fetchStatus();
    fetchSessions();
  }, []);

  // Fetch status of vectors and documents
  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
      }
    } catch (err) {
      console.error('Error fetching system status:', err);
    }
  };

  // Fetch active sessions from the backend
  const fetchSessions = async (selectLatest = false) => {
    try {
      const res = await fetch(`${API_URL}/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
        
        if (data.length > 0) {
          if (selectLatest || !activeSessionId) {
            // Select the last created/accessed session
            const targetSession = data[data.length - 1];
            setActiveSessionId(targetSession);
            fetchHistory(targetSession);
          }
        } else {
          setActiveSessionId(null);
          setMessages([]);
        }
      }
    } catch (err) {
      console.error('Error fetching sessions:', err);
    }
  };

  // Fetch chat history for selected session
  const fetchHistory = async (sessionId) => {
    try {
      const res = await fetch(`${API_URL}/sessions/${sessionId}`);
      if (res.ok) {
        const data = await res.json();
        // The backend returns standard API session records (list of {"role": "...", "content": "..."})
        // Since backend doesn't save source citations in the session history, we'll map them.
        setMessages(data);
        setExpandedSources({});
      }
    } catch (err) {
      console.error('Error fetching chat history:', err);
    }
  };

  // Scroll to bottom on message update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  // Create a new empty session
  const handleNewSession = () => {
    const newId = `session_${Date.now()}`;
    setActiveSessionId(newId);
    setMessages([]);
    setExpandedSources({});
  };

  // Switch between sessions
  const handleSelectSession = (sessionId) => {
    setActiveSessionId(sessionId);
    fetchHistory(sessionId);
  };

  // Delete a session
  const handleDeleteSession = async (e, sessionId) => {
    e.stopPropagation();
    try {
      const res = await fetch(`${API_URL}/sessions/${sessionId}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        if (activeSessionId === sessionId) {
          setActiveSessionId(null);
          setMessages([]);
        }
        fetchSessions();
      }
    } catch (err) {
      console.error('Error deleting session:', err);
    }
  };

  // Send message
  const handleSendMessage = async (e, customText = null) => {
    if (e) e.preventDefault();
    const textToSend = customText || inputText;
    if (!textToSend.trim()) return;

    let sessionId = activeSessionId;
    if (!sessionId) {
      sessionId = `session_${Date.now()}`;
      setActiveSessionId(sessionId);
    }

    // Add user message locally
    const updatedMessages = [...messages, { role: 'user', content: textToSend }];
    setMessages(updatedMessages);
    if (!customText) setInputText('');
    setIsLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: textToSend
        })
      });

      if (res.ok) {
        const data = await res.json();
        // Add assistant response
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.answer,
          sources: data.sources // include sources returned by API
        }]);
        // Refresh sessions to show the newly saved session
        fetchSessions();
      } else {
        const errorData = await res.json();
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: `⚠️ Error: ${errorData.detail || 'Failed to get response.'}`
        }]);
      }
    } catch (err) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `⚠️ Connection Error: Could not connect to the local server. Make sure the FastAPI backend is running on port 8000.`
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  // Build / Ingest Knowledge base
  const handleIngest = async () => {
    setIsIngesting(true);
    setIngestionStatusText('Extracting PDFs and building knowledge base...');
    
    try {
      const res = await fetch(`${API_URL}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      
      if (res.ok) {
        const data = await res.json();
        setIngestionStatusText(`Success! Loaded ${data.num_documents} pages (${data.num_chunks} chunks).`);
        setTimeout(() => {
          setIsIngesting(false);
          fetchStatus();
        }, 2000);
      } else {
        const errorData = await res.json();
        alert(`Ingestion failed: ${errorData.detail || 'Unknown error'}`);
        setIsIngesting(false);
      }
    } catch (err) {
      alert('Network error. Is the backend running?');
      setIsIngesting(false);
    }
  };

  const toggleSource = (msgIndex) => {
    setExpandedSources(prev => ({
      ...prev,
      [msgIndex]: !prev[msgIndex]
    }));
  };

  // Helper to render simple inline and block markdown styling
  const renderMarkdown = (text) => {
    if (!text) return null;
    const lines = text.split('\n');
    const elements = [];
    let currentList = [];
    let inList = false;

    const parseInline = (str) => {
      // Escape HTML entities to prevent issues
      let html = str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      
      // Bold **text**
      html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      // Italic *text*
      html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
      // Code `code`
      html = html.replace(/`(.*?)`/g, '<code>$1</code>');
      return <span dangerouslySetInnerHTML={{ __html: html }} />;
    };

    lines.forEach((line, index) => {
      const trimmed = line.trim();
      if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
        inList = true;
        currentList.push(trimmed.substring(2));
      } else {
        if (inList) {
          elements.push(
            <ul key={`list-${index}`}>
              {currentList.map((item, idx) => (
                <li key={idx}>{parseInline(item)}</li>
              ))}
            </ul>
          );
          currentList = [];
          inList = false;
        }

        if (trimmed.startsWith('### ')) {
          elements.push(<h3 key={index}>{parseInline(trimmed.substring(4))}</h3>);
        } else if (trimmed.startsWith('## ')) {
          elements.push(<h2 key={index}>{parseInline(trimmed.substring(3))}</h2>);
        } else if (trimmed.startsWith('# ')) {
          elements.push(<h1 key={index}>{parseInline(trimmed.substring(2))}</h1>);
        } else if (trimmed === '') {
          elements.push(<div key={index} style={{ height: '8px' }} />);
        } else {
          elements.push(<p key={index}>{parseInline(line)}</p>);
        }
      }
    });

    if (inList) {
      elements.push(
        <ul key={`list-end`}>
          {currentList.map((item, idx) => (
            <li key={idx}>{parseInline(item)}</li>
          ))}
        </ul>
      );
    }

    return elements;
  };

  const suggestions = [
    {
      icon: '🏋️',
      title: 'Endomorph Evolution',
      desc: 'What is the best workout and nutrition approach for endomorph body types?',
      prompt: 'What is the best workout structure and nutrition approach for an endomorph body type?'
    },
    {
      icon: '🥗',
      title: 'Nutrition & Diet',
      desc: 'Give me a high-protein breakfast and meal prep plan from the knowledge base.',
      prompt: 'Can you give me a high-protein breakfast recipe and some general diet principles mentioned in the documents?'
    },
    {
      icon: '💪',
      title: 'Form & Functional Training',
      desc: 'How do I perform squats and functional core exercises safely?',
      prompt: 'How do I perform barbell squats and functional core exercises properly? What form cues are mentioned?'
    }
  ];

  return (
    <div className="app-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <Dumbbell className="logo-icon" />
          <span className="logo-text">FitBot 🏋️</span>
        </div>

        <button className="new-chat-btn" onClick={handleNewSession}>
          <Plus size={16} />
          <span>New Session</span>
        </button>

        <div className="sessions-list-container">
          <div className="sessions-title">Chat Sessions</div>
          {sessions.length === 0 ? (
            <div style={{ padding: '12px', fontSize: '13px', color: 'var(--text-muted)', textAlign: 'center' }}>
              No active sessions.
            </div>
          ) : (
            sessions.map(id => (
              <div 
                key={id} 
                className={`session-item ${activeSessionId === id ? 'active' : ''}`}
                onClick={() => handleSelectSession(id)}
              >
                <div className="session-info">
                  <MessageSquare size={14} style={{ color: activeSessionId === id ? 'var(--accent-purple)' : 'var(--text-secondary)' }} />
                  <span className="session-name">{id.replace('session_', 'Session ')}</span>
                </div>
                <button 
                  className="session-delete-btn" 
                  onClick={(e) => handleDeleteSession(e, id)}
                  title="Delete Session"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Sidebar Footer Status Panel */}
        <div className="sidebar-footer">
          <div className="status-row">
            <span className="status-label">Knowledge Base:</span>
            <span className="status-value">
              {status.vectorstore_exists ? (
                <span className="badge-success">Ready</span>
              ) : (
                <span className="badge-warning">Missing Index</span>
              )}
            </span>
          </div>

          <div className="status-row">
            <span className="status-label">Ingested Files:</span>
            <span className="status-value" style={{ color: 'var(--text-secondary)' }}>
              {status.available_pdfs.length} PDFs
            </span>
          </div>

          <button 
            className="rebuild-btn" 
            onClick={handleIngest} 
            disabled={isIngesting}
          >
            <RefreshCw size={14} className={isIngesting ? 'spin' : ''} />
            <span>{status.vectorstore_exists ? 'Rebuild KB' : 'Build KB'}</span>
          </button>
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="main-chat">
        {/* Progress Overlay when Ingesting PDFs */}
        {isIngesting && (
          <div className="ingestion-overlay">
            <div className="spinner"></div>
            <div className="ingestion-progress-text">{ingestionStatusText}</div>
            <div className="ingestion-detail-text">Processing PDFs into vector embeddings. This takes a few seconds...</div>
          </div>
        )}

        {/* Header */}
        <div className="chat-header">
          <div className="chat-header-title">
            <h2>Gym Workout & Nutrition Expert</h2>
            <p>FitBot — Retrieval-Augmented Generation (Ollama Local Llama 3.1)</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--text-secondary)' }}>
            <Database size={14} style={{ color: 'var(--accent-purple)' }} />
            <span>Local DB</span>
          </div>
        </div>

        {/* Messages */}
        {messages.length === 0 ? (
          <div className="welcome-container">
            <div className="welcome-logo">🏋️</div>
            <h1 className="welcome-title">Welcome to FitBot</h1>
            <p className="welcome-subtitle">
              Ask any fitness or nutrition question. FitBot retrieves verified answers directly from your loaded PDF manuals.
            </p>

            <div className="suggestions-grid">
              {suggestions.map((s, idx) => (
                <div 
                  key={idx} 
                  className="suggestion-card" 
                  onClick={() => handleSendMessage(null, s.prompt)}
                >
                  <div className="suggestion-card-icon">{s.icon}</div>
                  <div className="suggestion-card-title">{s.title}</div>
                  <div className="suggestion-card-desc">{s.desc}</div>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="messages-container">
            {messages.map((msg, index) => (
              <div key={index} className={`message-wrapper ${msg.role === 'user' ? 'user' : 'bot'}`}>
                <div className="message-bubble">
                  {renderMarkdown(msg.content)}

                  {/* Sources display for bot responses */}
                  {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                    <div className="sources-container">
                      <button 
                        className="sources-toggle" 
                        onClick={() => toggleSource(index)}
                      >
                        <BookOpen size={12} />
                        <span>Sources ({msg.sources.length})</span>
                        {expandedSources[index] ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                      </button>

                      {expandedSources[index] && (
                        <div className="sources-list">
                          {msg.sources.map((src, srcIdx) => (
                            <div key={srcIdx} className="source-card">
                              <div className="source-meta">
                                <span className="source-doc">{src.filename}</span>
                                <span className="source-page">{src.page}</span>
                              </div>
                              <div className="source-snippet">
                                "{src.snippet}"
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {/* Typing Loader */}
            {isLoading && (
              <div className="message-wrapper bot">
                <div className="message-bubble" style={{ display: 'flex', alignItems: 'center' }}>
                  <div className="typing-indicator">
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                    <div className="typing-dot"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Input Bar */}
        <div className="input-form-container">
          <form className="input-form" onSubmit={(e) => handleSendMessage(e)}>
            <input 
              type="text" 
              className="chat-input"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Ask about exercises, macro splits, workouts..."
              disabled={isLoading || isIngesting}
            />
            <button 
              type="submit" 
              className="send-btn" 
              disabled={!inputText.trim() || isLoading || isIngesting}
              title="Send Message"
            >
              {isLoading ? <Loader2 className="spin" size={20} /> : <Send size={20} />}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default App;
